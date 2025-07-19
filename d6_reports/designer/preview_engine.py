"""
Preview Engine - P2-040 Dynamic Report Designer

Real-time preview generation system for report templates with support for
multiple output formats, live editing, and responsive design testing.

Features:
- Real-time preview rendering
- Multiple device/viewport testing
- Interactive preview with edit controls
- Format-specific previews (HTML, PDF, Mobile)
- Preview caching for performance
- Edit mode overlays
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .template_engine import RenderContext, TemplateConfig, TemplateEngine, TemplateResult, template_engine


class PreviewOptions(BaseModel):
    """Options for preview generation"""

    # Viewport settings
    viewport_width: int = Field(default=1200, ge=320, le=3840, description="Viewport width in pixels")
    viewport_height: int = Field(default=800, ge=240, le=2160, description="Viewport height in pixels")
    device_type: str = Field(default="desktop", description="Device type (desktop, tablet, mobile)")

    # Rendering settings
    format: str = Field(default="html", description="Preview format (html, pdf, mobile)")
    quality: str = Field(default="high", description="Preview quality (low, medium, high)")
    include_debug: bool = Field(default=False, description="Include debug information")

    # Interaction settings
    enable_edit_mode: bool = Field(default=True, description="Enable edit mode overlays")
    show_component_bounds: bool = Field(default=False, description="Show component boundaries")
    show_grid: bool = Field(default=False, description="Show design grid")

    # Performance settings
    cache_enabled: bool = Field(default=True, description="Enable preview caching")
    cache_duration_seconds: int = Field(default=300, description="Cache duration in seconds")

    # Content settings
    sample_data: Optional[Dict[str, Any]] = Field(default=None, description="Sample data for preview")
    data_source_overrides: Optional[Dict[str, str]] = Field(default=None, description="Data source overrides")


class PreviewResult(BaseModel):
    """Result of preview generation"""

    success: bool
    preview_id: str = Field(..., description="Unique preview identifier")
    template_id: str = Field(..., description="Template identifier")

    # Content
    html_content: Optional[str] = None
    css_content: Optional[str] = None
    javascript_content: Optional[str] = None

    # Metadata
    render_time_ms: int = 0
    cache_hit: bool = False
    viewport_width: int = 1200
    viewport_height: int = 800
    device_type: str = "desktop"

    # Errors and warnings
    error_message: Optional[str] = None
    warnings: List[str] = Field(default=[])

    # Edit mode data
    edit_mode_data: Optional[Dict[str, Any]] = None
    component_metadata: Optional[Dict[str, Any]] = None


@dataclass
class PreviewCache:
    """Cache entry for preview results"""

    preview_id: str
    template_id: str
    options_hash: str
    result: PreviewResult
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > self.expires_at

    def touch(self):
        """Update hit count and access time"""
        self.hit_count += 1


class PreviewEngine:
    """Real-time preview generation engine"""

    def __init__(self, template_engine: TemplateEngine = None):
        from .template_engine import template_engine as default_template_engine

        self.template_engine = template_engine or default_template_engine
        self.cache: Dict[str, PreviewCache] = {}
        self.cache_cleanup_interval = 300  # 5 minutes
        self._cleanup_task: Optional[asyncio.Task] = None

        # Device presets
        self.device_presets = {
            "desktop": {"width": 1200, "height": 800, "user_agent": "desktop"},
            "tablet": {"width": 768, "height": 1024, "user_agent": "tablet"},
            "mobile": {"width": 375, "height": 667, "user_agent": "mobile"},
            "large_desktop": {"width": 1920, "height": 1080, "user_agent": "desktop"},
            "small_mobile": {"width": 320, "height": 568, "user_agent": "mobile"},
        }

        # Cache cleanup will be started when first preview is generated

    def _start_cache_cleanup(self):
        """Start cache cleanup background task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.create_task(self._cache_cleanup_loop())
            except RuntimeError:
                # No event loop running, will start when needed
                pass

    async def _cache_cleanup_loop(self):
        """Background task for cache cleanup"""
        while True:
            try:
                await asyncio.sleep(self.cache_cleanup_interval)
                await self._cleanup_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cache cleanup error: {e}")

    async def _cleanup_cache(self):
        """Clean up expired cache entries"""
        now = datetime.utcnow()
        expired_keys = []

        for key, cache_entry in self.cache.items():
            if cache_entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            print(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _generate_options_hash(self, options: PreviewOptions) -> str:
        """Generate hash for preview options"""
        # Create a consistent hash from options
        options_dict = options.dict()
        options_str = json.dumps(options_dict, sort_keys=True)
        return str(hash(options_str))

    def _generate_preview_id(self, template_id: str, options: PreviewOptions) -> str:
        """Generate unique preview ID"""
        options_hash = self._generate_options_hash(options)
        timestamp = int(time.time())
        return f"preview_{template_id}_{options_hash}_{timestamp}"

    def _get_device_settings(self, device_type: str) -> Dict[str, Any]:
        """Get device-specific settings"""
        return self.device_presets.get(device_type, self.device_presets["desktop"])

    async def generate_preview(self, template_id: str, options: PreviewOptions) -> PreviewResult:
        """Generate preview for template"""
        start_time = datetime.utcnow()

        # Start cache cleanup if needed
        self._start_cache_cleanup()

        # Check cache first
        if options.cache_enabled:
            cache_key = f"{template_id}_{self._generate_options_hash(options)}"
            cached_result = self._get_cached_preview(cache_key)
            if cached_result:
                cached_result.cache_hit = True
                return cached_result

        try:
            # Get template
            template = self.template_engine.get_template(template_id)
            if not template:
                return PreviewResult(
                    success=False,
                    preview_id=self._generate_preview_id(template_id, options),
                    template_id=template_id,
                    error_message=f"Template not found: {template_id}",
                )

            # Apply device settings
            device_settings = self._get_device_settings(options.device_type)
            # Use device settings if viewport dimensions aren't explicitly set for mobile/tablet
            if options.device_type in ["mobile", "tablet"] and options.viewport_width == 1200:
                effective_width = device_settings["width"]
            else:
                effective_width = options.viewport_width

            if options.device_type in ["mobile", "tablet"] and options.viewport_height == 800:
                effective_height = device_settings["height"]
            else:
                effective_height = options.viewport_height

            # Prepare sample data
            sample_data = options.sample_data or self._generate_sample_data(template)

            # Create render context
            render_context = RenderContext(
                data=sample_data, render_mode=options.format, include_debug=options.include_debug
            )

            # Render template
            render_result = self.template_engine.render_template(template_id, render_context)

            if not render_result.success:
                return PreviewResult(
                    success=False,
                    preview_id=self._generate_preview_id(template_id, options),
                    template_id=template_id,
                    error_message=render_result.error_message,
                    warnings=render_result.warnings,
                )

            # Generate preview-specific content
            preview_html = self._enhance_html_for_preview(
                render_result.html_content, options, template, effective_width, effective_height
            )

            preview_css = self._enhance_css_for_preview(
                render_result.css_content, options, effective_width, effective_height
            )

            preview_js = self._generate_preview_javascript(options, template)

            # Generate edit mode data
            edit_mode_data = None
            component_metadata = None

            if options.enable_edit_mode:
                edit_mode_data = self._generate_edit_mode_data(template, options)
                component_metadata = self._generate_component_metadata(template)

            # Create result
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = PreviewResult(
                success=True,
                preview_id=self._generate_preview_id(template_id, options),
                template_id=template_id,
                html_content=preview_html,
                css_content=preview_css,
                javascript_content=preview_js,
                render_time_ms=int(execution_time),
                cache_hit=False,
                viewport_width=effective_width,
                viewport_height=effective_height,
                device_type=options.device_type,
                warnings=render_result.warnings,
                edit_mode_data=edit_mode_data,
                component_metadata=component_metadata,
            )

            # Cache result
            if options.cache_enabled:
                self._cache_preview(cache_key, result, options)

            return result

        except Exception as e:
            return PreviewResult(
                success=False,
                preview_id=self._generate_preview_id(template_id, options),
                template_id=template_id,
                error_message=f"Preview generation error: {str(e)}",
            )

    def _get_cached_preview(self, cache_key: str) -> Optional[PreviewResult]:
        """Get cached preview result"""
        if cache_key not in self.cache:
            return None

        cache_entry = self.cache[cache_key]

        if cache_entry.is_expired():
            del self.cache[cache_key]
            return None

        cache_entry.touch()
        return cache_entry.result

    def _cache_preview(self, cache_key: str, result: PreviewResult, options: PreviewOptions):
        """Cache preview result"""
        expires_at = datetime.utcnow() + timedelta(seconds=options.cache_duration_seconds)

        cache_entry = PreviewCache(
            preview_id=result.preview_id,
            template_id=result.template_id,
            options_hash=self._generate_options_hash(options),
            result=result,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        self.cache[cache_key] = cache_entry

    def _generate_sample_data(self, template: TemplateConfig) -> Dict[str, Any]:
        """Generate sample data for template"""
        sample_data = {}

        for data_source in template.data_sources:
            if data_source == "revenue_data":
                sample_data[data_source] = {"value": 125000, "currency": "USD", "change": 12.5, "trend": "up"}
            elif data_source == "performance_data":
                sample_data[data_source] = [
                    {"metric": "Revenue", "value": "$125,000", "change": "+12.5%"},
                    {"metric": "Customers", "value": "1,234", "change": "+8.2%"},
                    {"metric": "Conversion", "value": "3.45%", "change": "+0.8%"},
                ]
            elif data_source == "growth_data":
                sample_data[data_source] = {"value": 18.5, "unit": "%", "trend": "up"}
            elif data_source == "customer_data":
                sample_data[data_source] = {"value": 1234, "unit": "customers", "trend": "up"}
            elif data_source == "revenue_trend":
                sample_data[data_source] = {
                    "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
                    "values": [100000, 110000, 105000, 125000, 130000],
                }
            else:
                # Generic sample data
                sample_data[data_source] = {"value": 100, "label": f"Sample {data_source}", "trend": "stable"}

        return sample_data

    def _enhance_html_for_preview(
        self, html_content: str, options: PreviewOptions, template: TemplateConfig, width: int, height: int
    ) -> str:
        """Enhance HTML for preview with edit mode features"""
        if not html_content:
            return html_content

        # Add viewport meta tag
        viewport_meta = f'<meta name="viewport" content="width={width}, initial-scale=1.0">'

        # Add preview-specific CSS classes
        preview_class = f"preview-{options.device_type}"

        # Add edit mode overlays if enabled
        edit_overlays = ""
        if options.enable_edit_mode:
            edit_overlays = self._generate_edit_overlays(template, options)

        # Add component boundaries if enabled
        component_bounds = ""
        if options.show_component_bounds:
            component_bounds = self._generate_component_bounds(template)

        # Add grid if enabled
        grid_overlay = ""
        if options.show_grid:
            grid_overlay = self._generate_grid_overlay(width, height)

        # Insert enhancements
        enhanced_html = html_content

        # Add viewport meta tag
        if "<head>" in enhanced_html:
            enhanced_html = enhanced_html.replace("<head>", f"<head>\n{viewport_meta}")

        # Add preview class to body
        if "<body" in enhanced_html:
            enhanced_html = enhanced_html.replace(
                '<body class="report-body"', f'<body class="report-body {preview_class}"'
            )

        # Add overlays before closing body tag
        if "</body>" in enhanced_html:
            overlays = f"{edit_overlays}\n{component_bounds}\n{grid_overlay}"
            enhanced_html = enhanced_html.replace("</body>", f"{overlays}\n</body>")

        return enhanced_html

    def _enhance_css_for_preview(self, css_content: str, options: PreviewOptions, width: int, height: int) -> str:
        """Enhance CSS for preview with responsive and edit mode styles"""
        if not css_content:
            css_content = ""

        # Add responsive styles
        responsive_css = f"""
        /* Preview responsive styles */
        .preview-{options.device_type} {{
            max-width: {width}px;
            font-size: {self._get_font_size_for_device(options.device_type)};
        }}
        
        /* Edit mode styles */
        .edit-mode-overlay {{
            position: absolute;
            pointer-events: none;
            border: 2px dashed #007bff;
            background: rgba(0, 123, 255, 0.1);
            z-index: 1000;
        }}
        
        .component-bounds {{
            position: absolute;
            pointer-events: none;
            border: 1px solid #28a745;
            background: rgba(40, 167, 69, 0.05);
            z-index: 999;
        }}
        
        .grid-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            background-image: 
                linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            z-index: 998;
        }}
        
        .edit-handle {{
            position: absolute;
            width: 8px;
            height: 8px;
            background: #007bff;
            border: 1px solid white;
            cursor: grab;
            z-index: 1001;
        }}
        
        .edit-handle:hover {{
            background: #0056b3;
        }}
        
        /* Device-specific styles */
        @media (max-width: 768px) {{
            .preview-mobile .report-container {{
                padding: 20px;
                margin: 0;
            }}
            
            .preview-mobile .metric-container {{
                margin: 10px 0;
            }}
        }}
        """

        return css_content + "\n" + responsive_css

    def _get_font_size_for_device(self, device_type: str) -> str:
        """Get appropriate font size for device"""
        if device_type == "mobile":
            return "14px"
        elif device_type == "tablet":
            return "15px"
        else:
            return "16px"

    def _generate_preview_javascript(self, options: PreviewOptions, template: TemplateConfig) -> str:
        """Generate JavaScript for preview functionality"""
        if not options.enable_edit_mode:
            return ""

        js_content = f"""
        // Preview Engine JavaScript
        (function() {{
            'use strict';
            
            // Preview state
            let previewState = {{
                editMode: {str(options.enable_edit_mode).lower()},
                showBounds: {str(options.show_component_bounds).lower()},
                showGrid: {str(options.show_grid).lower()},
                selectedComponent: null,
                dragState: null
            }};
            
            // Component selection
            function selectComponent(componentId) {{
                // Remove previous selection
                document.querySelectorAll('.component-selected').forEach(el => {{
                    el.classList.remove('component-selected');
                }});
                
                // Add selection to new component
                const component = document.getElementById(componentId);
                if (component) {{
                    component.classList.add('component-selected');
                    previewState.selectedComponent = componentId;
                    
                    // Emit selection event
                    window.parent.postMessage({{
                        type: 'component_selected',
                        componentId: componentId
                    }}, '*');
                }}
            }}
            
            // Component hover
            function handleComponentHover(event) {{
                if (!previewState.editMode) return;
                
                const component = event.target.closest('[data-component-id]');
                if (component) {{
                    const componentId = component.getAttribute('data-component-id');
                    component.classList.add('component-hover');
                    
                    // Show component info
                    showComponentInfo(componentId, event.clientX, event.clientY);
                }}
            }}
            
            function handleComponentUnhover(event) {{
                if (!previewState.editMode) return;
                
                const component = event.target.closest('[data-component-id]');
                if (component) {{
                    component.classList.remove('component-hover');
                    hideComponentInfo();
                }}
            }}
            
            // Component info tooltip
            function showComponentInfo(componentId, x, y) {{
                let tooltip = document.getElementById('component-tooltip');
                if (!tooltip) {{
                    tooltip = document.createElement('div');
                    tooltip.id = 'component-tooltip';
                    tooltip.style.cssText = `
                        position: fixed;
                        background: #333;
                        color: white;
                        padding: 8px 12px;
                        border-radius: 4px;
                        font-size: 12px;
                        pointer-events: none;
                        z-index: 1002;
                        max-width: 200px;
                    `;
                    document.body.appendChild(tooltip);
                }}
                
                tooltip.textContent = `Component: ${{componentId}}`;
                tooltip.style.left = x + 10 + 'px';
                tooltip.style.top = y - 30 + 'px';
                tooltip.style.display = 'block';
            }}
            
            function hideComponentInfo() {{
                const tooltip = document.getElementById('component-tooltip');
                if (tooltip) {{
                    tooltip.style.display = 'none';
                }}
            }}
            
            // Initialize edit mode
            function initializeEditMode() {{
                if (!previewState.editMode) return;
                
                // Add component IDs and event listeners
                document.querySelectorAll('[class*="component-"]').forEach((el, index) => {{
                    const componentId = el.className.match(/component-([^\\s]+)/)?.[1] || `component-${{index}}`;
                    el.setAttribute('data-component-id', componentId);
                    
                    // Add event listeners
                    el.addEventListener('click', (e) => {{
                        e.preventDefault();
                        e.stopPropagation();
                        selectComponent(componentId);
                    }});
                    
                    el.addEventListener('mouseenter', handleComponentHover);
                    el.addEventListener('mouseleave', handleComponentUnhover);
                }});
                
                // Add CSS for edit mode
                const editModeCSS = `
                    [data-component-id] {{
                        cursor: pointer;
                        transition: all 0.2s ease;
                    }}
                    
                    [data-component-id]:hover {{
                        outline: 2px solid #007bff;
                        outline-offset: 2px;
                    }}
                    
                    .component-selected {{
                        outline: 2px solid #28a745 !important;
                        outline-offset: 2px;
                    }}
                    
                    .component-hover {{
                        background-color: rgba(0, 123, 255, 0.05) !important;
                    }}
                `;
                
                const style = document.createElement('style');
                style.textContent = editModeCSS;
                document.head.appendChild(style);
            }}
            
            // Message handling
            window.addEventListener('message', (event) => {{
                if (event.data.type === 'update_preview_options') {{
                    previewState = {{ ...previewState, ...event.data.options }};
                    updatePreviewDisplay();
                }}
            }});
            
            function updatePreviewDisplay() {{
                // Update grid visibility
                const grid = document.querySelector('.grid-overlay');
                if (grid) {{
                    grid.style.display = previewState.showGrid ? 'block' : 'none';
                }}
                
                // Update component bounds visibility
                document.querySelectorAll('.component-bounds').forEach(el => {{
                    el.style.display = previewState.showBounds ? 'block' : 'none';
                }});
            }}
            
            // Initialize on load
            document.addEventListener('DOMContentLoaded', initializeEditMode);
            
            // Export functions for parent frame
            window.previewAPI = {{
                selectComponent,
                getSelectedComponent: () => previewState.selectedComponent,
                updateOptions: (options) => {{
                    previewState = {{ ...previewState, ...options }};
                    updatePreviewDisplay();
                }}
            }};
        }})();
        """

        return js_content

    def _generate_edit_overlays(self, template: TemplateConfig, options: PreviewOptions) -> str:
        """Generate edit mode overlays"""
        if not options.enable_edit_mode:
            return ""

        overlays = []

        for i, component in enumerate(template.components):
            overlay = f"""
            <div class="edit-mode-overlay" 
                 data-component-id="{component.id}"
                 data-component-type="{component.type.value}"
                 style="display: none;">
                <div class="edit-handle edit-handle-nw" style="top: -4px; left: -4px;"></div>
                <div class="edit-handle edit-handle-ne" style="top: -4px; right: -4px;"></div>
                <div class="edit-handle edit-handle-sw" style="bottom: -4px; left: -4px;"></div>
                <div class="edit-handle edit-handle-se" style="bottom: -4px; right: -4px;"></div>
            </div>
            """
            overlays.append(overlay)

        return "\n".join(overlays)

    def _generate_component_bounds(self, template: TemplateConfig) -> str:
        """Generate component boundary overlays"""
        bounds = []

        for component in template.components:
            bound = f"""
            <div class="component-bounds"
                 data-component-id="{component.id}"
                 style="display: none;">
            </div>
            """
            bounds.append(bound)

        return "\n".join(bounds)

    def _generate_grid_overlay(self, width: int, height: int) -> str:
        """Generate design grid overlay"""
        return f"""
        <div class="grid-overlay" 
             style="width: {width}px; height: {height}px; display: none;">
        </div>
        """

    def _generate_edit_mode_data(self, template: TemplateConfig, options: PreviewOptions) -> Dict[str, Any]:
        """Generate edit mode data"""
        return {
            "enabled": options.enable_edit_mode,
            "show_bounds": options.show_component_bounds,
            "show_grid": options.show_grid,
            "components": [
                {
                    "id": comp.id,
                    "type": comp.type.value,
                    "title": comp.title,
                    "editable": comp.deletable,
                    "draggable": comp.draggable,
                    "resizable": comp.resizable,
                }
                for comp in template.components
            ],
        }

    def _generate_component_metadata(self, template: TemplateConfig) -> Dict[str, Any]:
        """Generate component metadata for editor"""
        metadata = {}

        for component in template.components:
            metadata[component.id] = {
                "type": component.type.value,
                "title": component.title,
                "description": component.description,
                "width": component.width,
                "height": component.height,
                "data_source": component.data_source,
                "custom_props": component.custom_props or {},
            }

        return metadata

    def get_device_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get available device presets"""
        return self.device_presets.copy()

    def clear_cache(self):
        """Clear preview cache"""
        self.cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = len(self.cache)
        expired_entries = sum(1 for entry in self.cache.values() if entry.is_expired())
        total_hits = sum(entry.hit_count for entry in self.cache.values())

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
            "total_hits": total_hits,
            "hit_rate": (total_hits / max(1, total_entries)) * 100,
        }

    def shutdown(self):
        """Shutdown the preview engine"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.cache.clear()


# Global preview engine instance
preview_engine = PreviewEngine()
