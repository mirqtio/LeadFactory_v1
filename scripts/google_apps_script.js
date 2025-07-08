/**
 * Google Apps Script for LeadFactory Scoring Configuration Sheet
 * 
 * This script provides functionality to submit configuration changes
 * to GitHub via Actions workflow.
 * 
 * Setup:
 * 1. Copy this script to your Google Sheet (Tools > Script editor)
 * 2. Replace placeholder values:
 *    - {{SHEET_ID}} with your actual Sheet ID
 *    - {{TAB_NAME}} with your configuration tab name
 *    - {{GH_PAT}} with a GitHub Personal Access Token
 * 3. Add a button to your sheet and assign it to submitToCI()
 */

// Configuration constants
const CONFIG = {
  SHEET_ID: "{{SHEET_ID}}",  // TODO: inject SHEET_ID
  TAB_NAME: "{{TAB_NAME}}",  // TODO: inject TAB_NAME
  GH_PAT: "{{GH_PAT}}",      // TODO: inject GH_PAT
  GITHUB_REPO: "anthrasite/LeadFactory_v1",
  WORKFLOW_FILE: "sheet_pull.yml",
  SHA_CELL: "Z1"  // Hidden cell for version tracking
};

/**
 * Get SHA from the designated cell
 */
function getSha() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const shaValue = sheet.getRange(CONFIG.SHA_CELL).getValue();
  
  // If no SHA exists, generate one based on timestamp
  if (!shaValue) {
    const newSha = generateSha();
    sheet.getRange(CONFIG.SHA_CELL).setValue(newSha);
    return newSha;
  }
  
  return shaValue.toString();
}

/**
 * Generate a new SHA based on timestamp
 */
function generateSha() {
  const timestamp = new Date().getTime();
  // Simple hash-like string (not cryptographic, just for versioning)
  return timestamp.toString(36).substr(-8);
}

/**
 * Main function to submit configuration to CI
 * This triggers the GitHub Actions workflow
 */
function submitToCI() {
  try {
    // Validate configuration first
    const validation = validateConfiguration();
    if (!validation.isValid) {
      SpreadsheetApp.getUi().alert(
        'Validation Error',
        `Configuration validation failed:\n\n${validation.errors.join('\n')}`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return;
    }
    
    // Get current SHA
    const sha = getSha();
    
    // Prepare workflow dispatch payload
    const payload = {
      ref: "main",
      inputs: {
        sheetId: CONFIG.SHEET_ID,
        tab: CONFIG.TAB_NAME,
        sha: sha
      }
    };
    
    // GitHub API endpoint for workflow dispatch
    const url = `https://api.github.com/repos/${CONFIG.GITHUB_REPO}/actions/workflows/${CONFIG.WORKFLOW_FILE}/dispatches`;
    
    // Make API request
    const options = {
      method: "POST",
      headers: {
        "Authorization": `token ${CONFIG.GH_PAT}`,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(url, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode === 204) {
      // Success - workflow triggered
      SpreadsheetApp.getUi().alert(
        'Success',
        `Configuration submitted successfully!\n\nSHA: ${sha}\n\nA pull request will be created shortly.`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      
      // Update last submission timestamp
      updateLastSubmission(sha);
    } else {
      // Error occurred
      const errorMsg = response.getContentText();
      SpreadsheetApp.getUi().alert(
        'Error',
        `Failed to submit configuration:\n\nStatus: ${responseCode}\n${errorMsg}`,
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    }
    
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'Error',
      `An error occurred: ${error.toString()}`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * Validate the configuration before submission
 */
function validateConfiguration() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const errors = [];
  
  // Check tier configuration (A2:C6)
  const tierRange = sheet.getRange("A2:C6");
  const tierValues = tierRange.getValues();
  
  const requiredTiers = ['A', 'B', 'C', 'D'];
  const foundTiers = [];
  
  for (let i = 0; i < tierValues.length; i++) {
    const row = tierValues[i];
    if (row[0] && row[2]) {  // Has tier name and label
      foundTiers.push(row[2]);
      
      // Validate min score is numeric
      const minScore = parseFloat(row[1]);
      if (isNaN(minScore) || minScore < 0 || minScore > 100) {
        errors.push(`Invalid min score for tier ${row[2]}: ${row[1]}`);
      }
    }
  }
  
  // Check all required tiers are present
  const missingTiers = requiredTiers.filter(t => !foundTiers.includes(t));
  if (missingTiers.length > 0) {
    errors.push(`Missing required tiers: ${missingTiers.join(', ')}`);
  }
  
  // Check component weights (A10:E50)
  const compRange = sheet.getRange("A10:E50");
  const compValues = compRange.getValues();
  
  let totalComponentWeight = 0;
  const componentWeights = {};
  
  for (let i = 0; i < compValues.length; i++) {
    const row = compValues[i];
    
    // Component row has name in A and weight in B
    if (row[0] && row[1] && !row[2]) {
      const weight = parseFloat(row[1]);
      if (!isNaN(weight)) {
        totalComponentWeight += weight;
        componentWeights[row[0]] = weight;
      }
    }
  }
  
  // Check total weight is close to 1.0
  const weightDiff = Math.abs(totalComponentWeight - 1.0);
  if (weightDiff > 0.05) {
    errors.push(`Component weights sum to ${totalComponentWeight.toFixed(3)}, must be 1.0 ± 0.05`);
  } else if (weightDiff > 0.005) {
    // This is a warning, but we'll allow it
    console.log(`Warning: Component weights sum to ${totalComponentWeight.toFixed(3)}, should be 1.0 ± 0.005`);
  }
  
  return {
    isValid: errors.length === 0,
    errors: errors
  };
}

/**
 * Update last submission info
 */
function updateLastSubmission(sha) {
  const sheet = SpreadsheetApp.getActiveSheet();
  const timestamp = new Date().toISOString();
  
  // Store in hidden cells
  sheet.getRange("AA1").setValue("Last Submission:");
  sheet.getRange("AB1").setValue(timestamp);
  sheet.getRange("AA2").setValue("SHA:");
  sheet.getRange("AB2").setValue(sha);
}

/**
 * Menu creation for easy access
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('LeadFactory Config')
    .addItem('Submit to GitHub', 'submitToCI')
    .addItem('Validate Configuration', 'showValidation')
    .addSeparator()
    .addItem('About', 'showAbout')
    .addToUi();
}

/**
 * Show validation results
 */
function showValidation() {
  const validation = validateConfiguration();
  
  if (validation.isValid) {
    SpreadsheetApp.getUi().alert(
      'Validation Passed',
      'Configuration is valid and ready for submission.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    SpreadsheetApp.getUi().alert(
      'Validation Failed',
      `Please fix the following issues:\n\n${validation.errors.join('\n')}`,
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * Show about dialog
 */
function showAbout() {
  const htmlContent = `
    <div style="font-family: Arial, sans-serif; padding: 20px;">
      <h2>LeadFactory Scoring Configuration</h2>
      <p>This sheet controls the scoring weights and tier thresholds for LeadFactory.</p>
      
      <h3>How to use:</h3>
      <ol>
        <li>Edit the tier thresholds (rows 2-6)</li>
        <li>Edit component weights (starting row 10)</li>
        <li>Ensure component weights sum to 1.0 (±0.005)</li>
        <li>Click "Submit to GitHub" to create a pull request</li>
      </ol>
      
      <h3>Important:</h3>
      <ul>
        <li>All tier labels (A, B, C, D) must be present</li>
        <li>Component weights must sum to approximately 1.0</li>
        <li>Factor weights within each component must also sum to 1.0</li>
      </ul>
      
      <p><em>Version tracking SHA: ${getSha()}</em></p>
    </div>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(400)
    .setHeight(400);
    
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'About LeadFactory Config');
}