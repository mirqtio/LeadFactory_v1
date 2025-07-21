"""
Unit Economics PDF Generation Service - P2-020

Executive-grade PDF reports for unit economics with charts and professional formatting.

Acceptance Criteria:
- PDF export from unit economics endpoint
- Executive-grade charts and formatting
- Multi-page reports with comprehensive metrics
- Professional branding and layout
"""

import base64
import logging
import time
from datetime import datetime

import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


class UnitEconomicsPDFService:
    """Service for generating professional unit economics PDF reports"""

    def __init__(self):
        """Initialize PDF service with templates and configuration"""
        self.template_env = Environment(loader=FileSystemLoader("d10_analytics/templates"), autoescape=True)

    async def generate_unit_economics_pdf(
        self,
        unit_econ_data: list[dict],
        summary: dict,
        date_range: dict[str, str],
        request_id: str,
        include_charts: bool = True,
        include_detailed_analysis: bool = True,
    ) -> bytes:
        """
        Generate comprehensive unit economics PDF report

        Args:
            unit_econ_data: Daily unit economics data
            summary: Aggregated summary metrics
            date_range: Start and end dates
            request_id: Request identifier
            include_charts: Whether to include visualizations
            include_detailed_analysis: Whether to include detailed analysis

        Returns:
            PDF content as bytes
        """
        try:
            start_time = time.time()
            logger.info(f"Generating unit economics PDF for request {request_id}")

            # Generate charts if requested
            charts = {}
            if include_charts and unit_econ_data:
                chart_start = time.time()
                charts = await self._generate_charts(unit_econ_data, summary)
                chart_time = time.time() - chart_start
                logger.info(f"Chart generation completed in {chart_time:.2f}s")

            # Prepare data for template with defaults for empty data
            default_summary = {
                "overall_roi_percentage": None,
                "avg_cac_cents": None,
                "avg_ltv_cents": None,
                "avg_cpl_cents": None,
                "conversion_rate_pct": None,
                "total_profit_cents": None,
                "total_cost_cents": 0,
                "total_revenue_cents": 0,
                "total_leads": 0,
                "total_conversions": 0,
            }
            # Merge with provided summary, using defaults for missing values
            merged_summary = {**default_summary, **summary}

            template_data = {
                "report_title": "Unit Economics Analysis Report",
                "generation_date": datetime.utcnow().strftime("%B %d, %Y"),
                "date_range": date_range,
                "summary": merged_summary,
                "daily_data": unit_econ_data,
                "charts": charts,
                "request_id": request_id,
                "include_detailed_analysis": include_detailed_analysis,
                "key_insights": self._generate_insights(unit_econ_data, merged_summary),
                "recommendations": self._generate_recommendations(merged_summary),
                "data_freshness": self._calculate_data_freshness(unit_econ_data, date_range),
            }

            # Render HTML template
            template_start = time.time()
            template = self.template_env.get_template("unit_economics_report.html")
            html_content = template.render(**template_data)
            template_time = time.time() - template_start
            logger.info(f"Template rendering completed in {template_time:.2f}s")

            # Convert HTML to PDF using Playwright
            pdf_start = time.time()
            pdf_content = await self._html_to_pdf(html_content)
            pdf_time = time.time() - pdf_start
            logger.info(f"PDF conversion completed in {pdf_time:.2f}s")

            total_time = time.time() - start_time
            logger.info(f"Successfully generated PDF for request {request_id} in {total_time:.2f}s total")

            # Performance validation - ensure O(n) complexity
            data_size = len(unit_econ_data) if unit_econ_data else 0
            if data_size > 0:
                time_per_record = total_time / data_size
                if time_per_record > 0.1:  # More than 100ms per record indicates potential performance issue
                    logger.warning(f"Performance concern: {time_per_record:.3f}s per record for {data_size} records")

            return pdf_content

        except Exception as e:
            logger.error(f"Error generating PDF for request {request_id}: {str(e)}")
            raise

    async def _generate_charts(self, daily_data: list[dict], summary: dict) -> dict[str, str]:
        """Generate base64-encoded charts for PDF inclusion"""
        charts = {}

        try:
            # Extract data for charts
            dates = [item.get("date", "") for item in daily_data]
            costs = [item.get("total_cost_cents", 0) / 100 for item in daily_data]  # Convert to dollars
            revenues = [item.get("total_revenue_cents", 0) / 100 for item in daily_data]
            profits = [item.get("profit_cents", 0) / 100 for item in daily_data]
            leads = [item.get("total_leads", 0) for item in daily_data]
            conversions = [item.get("total_conversions", 0) for item in daily_data]

            # 1. Revenue vs Cost Trend
            fig_revenue_cost = go.Figure()
            fig_revenue_cost.add_trace(
                go.Scatter(
                    x=dates, y=revenues, mode="lines+markers", name="Revenue", line=dict(color="#2E8B57", width=3)
                )
            )
            fig_revenue_cost.add_trace(
                go.Scatter(x=dates, y=costs, mode="lines+markers", name="Cost", line=dict(color="#DC143C", width=3))
            )

            fig_revenue_cost.update_layout(
                title="Revenue vs Cost Trend",
                xaxis_title="Date",
                yaxis_title="Amount ($)",
                font=dict(size=12),
                height=400,
                showlegend=True,
                plot_bgcolor="white",
                paper_bgcolor="white",
            )

            charts["revenue_cost_trend"] = self._fig_to_base64(fig_revenue_cost)

            # 2. Profit Trend
            fig_profit = go.Figure()
            fig_profit.add_trace(
                go.Scatter(
                    x=dates,
                    y=profits,
                    mode="lines+markers",
                    name="Daily Profit",
                    line=dict(color="#4169E1", width=3),
                    fill="tonexty",
                )
            )

            fig_profit.update_layout(
                title="Daily Profit Trend",
                xaxis_title="Date",
                yaxis_title="Profit ($)",
                font=dict(size=12),
                height=400,
                plot_bgcolor="white",
                paper_bgcolor="white",
            )

            charts["profit_trend"] = self._fig_to_base64(fig_profit)

            # 3. Leads vs Conversions
            fig_funnel = make_subplots(specs=[[{"secondary_y": True}]])

            fig_funnel.add_trace(
                go.Bar(x=dates, y=leads, name="Leads", marker_color="#87CEEB"),
                secondary_y=False,
            )

            fig_funnel.add_trace(
                go.Scatter(
                    x=dates,
                    y=conversions,
                    mode="lines+markers",
                    name="Conversions",
                    line=dict(color="#FF6347", width=3),
                ),
                secondary_y=True,
            )

            fig_funnel.update_layout(
                title="Lead Generation vs Conversions",
                font=dict(size=12),
                height=400,
                plot_bgcolor="white",
                paper_bgcolor="white",
            )

            fig_funnel.update_yaxes(title_text="Number of Leads", secondary_y=False)
            fig_funnel.update_yaxes(title_text="Number of Conversions", secondary_y=True)

            charts["leads_conversions"] = self._fig_to_base64(fig_funnel)

            # 4. Key Metrics Summary (Gauge Charts)
            metrics_fig = make_subplots(
                rows=2,
                cols=2,
                subplot_titles=("ROI %", "CAC ($)", "CPL ($)", "LTV ($)"),
                specs=[[{"type": "indicator"}, {"type": "indicator"}], [{"type": "indicator"}, {"type": "indicator"}]],
            )

            # ROI Gauge
            roi = summary.get("overall_roi_percentage", 0)
            metrics_fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=roi,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "ROI %"},
                    gauge={
                        "axis": {"range": [None, 500]},
                        "bar": {"color": "darkblue"},
                        "steps": [
                            {"range": [0, 100], "color": "lightgray"},
                            {"range": [100, 300], "color": "yellow"},
                            {"range": [300, 500], "color": "green"},
                        ],
                        "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 200},
                    },
                ),
                row=1,
                col=1,
            )

            # CAC Gauge
            cac = (summary.get("avg_cac_cents", 0) or 0) / 100
            metrics_fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=cac,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "CAC ($)"},
                    gauge={
                        "axis": {"range": [0, 50]},
                        "bar": {"color": "darkred"},
                        "steps": [
                            {"range": [0, 10], "color": "green"},
                            {"range": [10, 25], "color": "yellow"},
                            {"range": [25, 50], "color": "red"},
                        ],
                    },
                ),
                row=1,
                col=2,
            )

            # CPL Gauge
            cpl = (summary.get("avg_cpl_cents", 0) or 0) / 100
            metrics_fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=cpl,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "CPL ($)"},
                    gauge={
                        "axis": {"range": [0, 5]},
                        "bar": {"color": "darkorange"},
                        "steps": [
                            {"range": [0, 1], "color": "green"},
                            {"range": [1, 3], "color": "yellow"},
                            {"range": [3, 5], "color": "red"},
                        ],
                    },
                ),
                row=2,
                col=1,
            )

            # LTV Gauge
            ltv = (summary.get("avg_ltv_cents", 0) or 0) / 100
            metrics_fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=ltv,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "LTV ($)"},
                    gauge={
                        "axis": {"range": [0, 500]},
                        "bar": {"color": "darkgreen"},
                        "steps": [
                            {"range": [0, 200], "color": "red"},
                            {"range": [200, 400], "color": "yellow"},
                            {"range": [400, 500], "color": "green"},
                        ],
                    },
                ),
                row=2,
                col=2,
            )

            metrics_fig.update_layout(title="Key Unit Economics Metrics", height=600, font=dict(size=10))

            charts["metrics_gauges"] = self._fig_to_base64(metrics_fig)

            logger.info(f"Generated {len(charts)} charts for PDF report")

        except Exception as e:
            logger.error(f"Error generating charts: {str(e)}")
            # Return empty charts dict on error

        return charts

    def _fig_to_base64(self, fig) -> str:
        """Convert plotly figure to base64 string for HTML embedding"""
        try:
            img_bytes = fig.to_image(format="png", width=800, height=400, scale=2)
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            return f"data:image/png;base64,{img_base64}"
        except Exception as e:
            logger.error(f"Error converting figure to base64: {str(e)}")
            return ""

    def _generate_insights(self, daily_data: list[dict], summary: dict) -> list[str]:
        """Generate key insights based on unit economics data"""
        insights = []

        try:
            # ROI Analysis
            roi = summary.get("overall_roi_percentage")
            if roi is not None:
                if roi > 300:
                    insights.append(f"🎯 Excellent ROI of {roi:.1f}% indicates highly profitable operations")
                elif roi > 100:
                    insights.append(f"✅ Positive ROI of {roi:.1f}% shows profitable customer acquisition")
                elif roi > 0:
                    insights.append(f"⚠️ Low ROI of {roi:.1f}% suggests room for optimization")
                else:
                    insights.append(f"🚨 Negative ROI of {roi:.1f}% indicates unprofitable operations")

            # CAC vs LTV Analysis
            cac = summary.get("avg_cac_cents", 0) or 0
            ltv = summary.get("avg_ltv_cents", 0) or 0

            if cac > 0 and ltv > 0:
                ltv_cac_ratio = ltv / cac
                if ltv_cac_ratio > 3:
                    insights.append(f"💰 Strong LTV:CAC ratio of {ltv_cac_ratio:.1f}:1 indicates healthy unit economics")
                elif ltv_cac_ratio > 1:
                    insights.append(f"📈 LTV:CAC ratio of {ltv_cac_ratio:.1f}:1 shows positive customer value")
                else:
                    insights.append(f"⚠️ LTV:CAC ratio of {ltv_cac_ratio:.1f}:1 below recommended 3:1 threshold")

            # Conversion Rate Analysis
            conversion_rate = summary.get("conversion_rate_pct", 0)
            if conversion_rate > 5:
                insights.append(
                    f"🔥 High conversion rate of {conversion_rate:.1f}% demonstrates strong product-market fit"
                )
            elif conversion_rate > 2:
                insights.append(f"👍 Solid conversion rate of {conversion_rate:.1f}% within industry standards")
            else:
                insights.append(f"📊 Conversion rate of {conversion_rate:.1f}% has optimization potential")

            # Volume Analysis
            total_leads = summary.get("total_leads", 0)
            total_conversions = summary.get("total_conversions", 0)

            if total_leads > 1000:
                insights.append(f"📈 Strong lead volume of {total_leads:,} leads demonstrates effective top-of-funnel")

            if total_conversions > 50:
                insights.append(
                    f"💎 Healthy conversion volume of {total_conversions} customers shows scalable acquisition"
                )

        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            insights.append("Unable to generate insights due to data processing error")

        return insights[:5]  # Limit to top 5 insights

    def _generate_recommendations(self, summary: dict) -> list[str]:
        """Generate actionable recommendations based on unit economics"""
        recommendations = []

        try:
            roi = summary.get("overall_roi_percentage", 0)
            cac = (summary.get("avg_cac_cents", 0) or 0) / 100
            conversion_rate = summary.get("conversion_rate_pct", 0)

            # ROI-based recommendations
            if roi < 100:
                recommendations.append("🎯 Focus on reducing customer acquisition cost through channel optimization")
                recommendations.append("💡 Increase pricing or upsell opportunities to improve unit economics")

            # CAC optimization
            if cac > 20:
                recommendations.append("💰 High CAC suggests need for more efficient marketing channels")
                recommendations.append("🔍 Analyze top-performing campaigns and reallocate budget accordingly")

            # Conversion optimization
            if conversion_rate < 3:
                recommendations.append("🚀 Improve conversion rates through landing page optimization and A/B testing")
                recommendations.append("📞 Implement lead nurturing sequences to increase conversion rates")

            # Scale recommendations
            if roi > 200 and conversion_rate > 3:
                recommendations.append("⚡ Strong metrics indicate opportunity to scale marketing investment")
                recommendations.append("📊 Consider expanding to similar customer segments or geographic markets")

            # Always include monitoring recommendation
            recommendations.append("📈 Implement weekly unit economics monitoring to track trend changes")

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations.append("Contact analytics team for customized optimization recommendations")

        return recommendations[:6]  # Limit to top 6 recommendations

    def _calculate_data_freshness(self, unit_econ_data: list[dict], date_range: dict[str, str]) -> dict:
        """Calculate data freshness indicators for the report"""
        try:
            now = datetime.utcnow()

            # Parse end date from date range
            end_date_str = date_range.get("end_date", "")
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                days_since_end = (now - end_date).days
            else:
                days_since_end = 0

            # Calculate freshness status
            if days_since_end <= 1:
                freshness_status = "fresh"
                freshness_color = "#28a745"  # Green
                freshness_text = "📊 Data is current (within 24 hours)"
            elif days_since_end <= 7:
                freshness_status = "recent"
                freshness_color = "#ffc107"  # Yellow
                freshness_text = f"⏰ Data is {days_since_end} days old"
            else:
                freshness_status = "stale"
                freshness_color = "#dc3545"  # Red
                freshness_text = f"⚠️ Data is {days_since_end} days old - consider refreshing"

            # Calculate data completeness
            total_possible_days = len(unit_econ_data) if unit_econ_data else 0
            complete_days = sum(1 for day in unit_econ_data if day.get("total_leads", 0) > 0)
            completeness_pct = (complete_days / total_possible_days * 100) if total_possible_days > 0 else 0

            return {
                "status": freshness_status,
                "color": freshness_color,
                "text": freshness_text,
                "days_since_end": days_since_end,
                "completeness_pct": completeness_pct,
                "last_update": now.strftime("%Y-%m-%d %H:%M UTC"),
            }

        except Exception as e:
            logger.error(f"Error calculating data freshness: {str(e)}")
            return {
                "status": "unknown",
                "color": "#6c757d",
                "text": "📊 Data freshness status unavailable",
                "days_since_end": 0,
                "completeness_pct": 0,
                "last_update": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            }

    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Convert HTML content to PDF using Playwright"""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Set content and wait for images to load
                await page.set_content(html_content, wait_until="networkidle")

                # Generate PDF with professional settings
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
                )

                await browser.close()
                return pdf_bytes

        except Exception as e:
            logger.error(f"Error converting HTML to PDF: {str(e)}")
            raise
