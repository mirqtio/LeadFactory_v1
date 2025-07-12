// Template Studio Editor JavaScript

let editor;
let currentTemplate = null;
let originalContent = {};
let wsConnection = null;
let previewDebounceTimer = null;

// Initialize Monaco Editor
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' } });

require(['vs/editor/editor.main'], function () {
    // Register Jinja2 language
    monaco.languages.register({ id: 'jinja2' });
    
    // Define Jinja2 syntax highlighting
    monaco.languages.setMonarchTokensProvider('jinja2', {
        tokenizer: {
            root: [
                [/\{\{/, { token: 'delimiter.jinja2', next: '@expression' }],
                [/\{%/, { token: 'delimiter.jinja2', next: '@statement' }],
                [/\{#/, { token: 'comment.jinja2', next: '@comment' }],
                [/<[^>]+>/, 'tag.html'],
                [/[^<{]+/, 'text'],
            ],
            expression: [
                [/\}\}/, { token: 'delimiter.jinja2', next: '@pop' }],
                [/\|/, 'operator.jinja2'],
                [/\w+/, 'variable.jinja2'],
                [/[^}]+/, 'variable.jinja2']
            ],
            statement: [
                [/%\}/, { token: 'delimiter.jinja2', next: '@pop' }],
                [/(if|for|endif|endfor|else|elif|set|include|extends|block|endblock|macro|endmacro|call|filter|endfilter|with|endwith)/, 'keyword.jinja2'],
                [/\w+/, 'identifier.jinja2'],
                [/[^%]+/, 'string.jinja2']
            ],
            comment: [
                [/#\}/, { token: 'comment.jinja2', next: '@pop' }],
                [/[^#]+/, 'comment.jinja2']
            ]
        }
    });
    
    // Create editor
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: '<!-- Select a template to edit -->',
        language: 'jinja2',
        theme: 'vs',
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: 'on',
        renderWhitespace: 'boundary',
        scrollBeyondLastLine: false,
    });
    
    // Initialize the app
    init();
});

// Initialize application
async function init() {
    // Load templates
    await loadTemplates();
    
    // Set up WebSocket for real-time preview
    setupWebSocket();
    
    // Set up event listeners
    setupEventListeners();
}

// Load template list
async function loadTemplates() {
    try {
        const response = await fetch('/api/template-studio/templates');
        const templates = await response.json();
        
        const listEl = document.getElementById('templateList');
        listEl.innerHTML = '';
        
        templates.forEach(template => {
            const item = document.createElement('div');
            item.className = 'template-item';
            item.dataset.templateName = template.name;
            
            item.innerHTML = `
                <div class="name">${template.name}</div>
                <div class="meta">
                    SHA: ${template.git.sha} | 
                    ${new Date(template.git.date).toLocaleDateString()}
                </div>
            `;
            
            item.addEventListener('click', () => loadTemplate(template.name));
            listEl.appendChild(item);
        });
    } catch (error) {
        console.error('Failed to load templates:', error);
        showStatus('Failed to load templates', 'error');
    }
}

// Load a specific template
async function loadTemplate(templateName) {
    try {
        const response = await fetch(`/api/template-studio/templates/${templateName}`);
        const data = await response.json();
        
        currentTemplate = templateName;
        originalContent[templateName] = data.content;
        
        // Update UI
        document.getElementById('currentTemplate').textContent = templateName;
        editor.setValue(data.content);
        
        // Update active state
        document.querySelectorAll('.template-item').forEach(item => {
            item.classList.toggle('active', item.dataset.templateName === templateName);
        });
        
        // Enable buttons
        document.getElementById('validateBtn').disabled = false;
        document.getElementById('previewBtn').disabled = false;
        updateSaveButton();
        
        // Auto-preview
        await previewTemplate();
    } catch (error) {
        console.error('Failed to load template:', error);
        showStatus('Failed to load template', 'error');
    }
}

// Set up WebSocket connection
function setupWebSocket() {
    const wsUrl = `ws://${window.location.host}/api/template-studio/ws/preview`;
    wsConnection = new WebSocket(wsUrl);
    
    wsConnection.onopen = () => {
        console.log('WebSocket connected');
    };
    
    wsConnection.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.success) {
            updatePreview(data.content);
            showStatus('Preview updated', 'success');
        } else if (data.error) {
            showStatus(data.error, 'error');
        }
    };
    
    wsConnection.onerror = (error) => {
        console.error('WebSocket error:', error);
        showStatus('WebSocket connection error', 'error');
    };
    
    wsConnection.onclose = () => {
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 3 seconds
        setTimeout(setupWebSocket, 3000);
    };
}

// Set up event listeners
function setupEventListeners() {
    // Editor change listener with debouncing
    editor.onDidChangeModelContent(() => {
        updateSaveButton();
        
        // Debounce preview updates
        clearTimeout(previewDebounceTimer);
        previewDebounceTimer = setTimeout(() => {
            if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                sendPreviewUpdate();
            }
        }, 500); // 500ms debounce
    });
    
    // Button listeners
    document.getElementById('validateBtn').addEventListener('click', validateTemplate);
    document.getElementById('previewBtn').addEventListener('click', previewTemplate);
    document.getElementById('saveBtn').addEventListener('click', openPRDialog);
    
    // PR form
    document.getElementById('prForm').addEventListener('submit', createPullRequest);
}

// Validate template
async function validateTemplate() {
    const content = editor.getValue();
    
    try {
        const response = await fetch('/api/template-studio/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        
        const result = await response.json();
        
        if (result.valid) {
            showStatus(`Valid template. Variables: ${result.variables.join(', ') || 'none'}`, 'success');
        } else {
            showStatus(`Invalid template: ${result.errors.join(', ')}`, 'error');
        }
    } catch (error) {
        console.error('Validation error:', error);
        showStatus('Validation failed', 'error');
    }
}

// Preview template
async function previewTemplate() {
    if (!currentTemplate) return;
    
    const startTime = performance.now();
    document.getElementById('previewStatus').textContent = 'Rendering...';
    
    try {
        const response = await fetch('/api/template-studio/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_name: currentTemplate,
                sample_data: null // Use default sample data
            })
        });
        
        const result = await response.json();
        const renderTime = performance.now() - startTime;
        
        document.getElementById('renderTime').textContent = `${renderTime.toFixed(0)}ms`;
        
        if (result.success) {
            updatePreview(result.content);
            document.getElementById('previewStatus').textContent = 'Ready';
            
            if (renderTime > 500) {
                showStatus('Warning: Preview took > 500ms', 'warning');
            }
        } else {
            document.getElementById('previewStatus').textContent = 'Error';
            showStatus(result.error, 'error');
        }
    } catch (error) {
        console.error('Preview error:', error);
        document.getElementById('previewStatus').textContent = 'Error';
        showStatus('Preview failed', 'error');
    }
}

// Send preview update via WebSocket
function sendPreviewUpdate() {
    if (!currentTemplate || !wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
        return;
    }
    
    const content = editor.getValue();
    
    wsConnection.send(JSON.stringify({
        template_name: currentTemplate,
        content: content,
        sample_data: null // Use default
    }));
}

// Update preview iframe
function updatePreview(html) {
    const preview = document.getElementById('preview');
    const doc = preview.contentDocument || preview.contentWindow.document;
    
    doc.open();
    doc.write(html);
    doc.close();
}

// Update save button state
function updateSaveButton() {
    if (!currentTemplate) return;
    
    const currentContent = editor.getValue();
    const hasChanges = currentContent !== originalContent[currentTemplate];
    
    document.getElementById('saveBtn').disabled = !hasChanges;
}

// Open PR dialog
function openPRDialog() {
    document.getElementById('prDialog').style.display = 'flex';
    document.getElementById('commitMessage').focus();
}

// Close PR dialog
function closePRDialog() {
    document.getElementById('prDialog').style.display = 'none';
    document.getElementById('prForm').reset();
}

// Create pull request
async function createPullRequest(event) {
    event.preventDefault();
    
    const commitMessage = document.getElementById('commitMessage').value;
    const content = editor.getValue();
    
    try {
        const response = await fetch('/api/template-studio/create-pr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                changes: {
                    [currentTemplate]: content
                },
                user: 'admin', // TODO: Get from auth
                commit_message: commitMessage
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showStatus(`Pull request created: ${result.pr_url}`, 'success');
            
            // Update original content
            originalContent[currentTemplate] = content;
            updateSaveButton();
            
            // Close dialog
            closePRDialog();
            
            // Open PR in new tab
            if (result.pr_url) {
                window.open(result.pr_url, '_blank');
            }
        } else {
            showStatus(`Failed to create PR: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('PR creation error:', error);
        showStatus('Failed to create pull request', 'error');
    }
}

// Show status message
function showStatus(message, type = 'info') {
    // In a real app, this would show a toast notification
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Update preview status for errors
    if (type === 'error') {
        document.getElementById('previewStatus').textContent = message;
        document.getElementById('previewStatus').className = 'status-error';
    }
}