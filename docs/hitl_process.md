# Human-in-the-Loop (HITL) Process Documentation

## Overview

The LeadFactory system implements Human-in-the-Loop checkpoints for critical operations that could have significant business impact or require human judgment. This document outlines when and how HITL processes are triggered.

## HITL Checkpoints

### 1. Data Purchase Decisions (P1-021)

**When Triggered:**
- Before purchasing data from external providers (Data Axle, etc.)
- When total cost exceeds $100 for a single request
- When purchasing data for more than 1000 businesses

**Process:**
1. System generates purchase summary with:
   - Number of businesses
   - Estimated cost
   - Data quality metrics
   - Purchase justification
2. Sends notification to designated approver
3. Waits for approval (max 24 hours)
4. Proceeds only with explicit approval

**Approval Methods:**
- Email link with approve/reject buttons
- Admin dashboard approval queue
- CLI command: `leadfactory approve-purchase <request-id>`

### 2. Email Campaign Launch (P1-017)

**When Triggered:**
- Before sending emails to more than 100 recipients
- When using new email templates
- When targeting high-value segments

**Process:**
1. System generates campaign preview:
   - Sample emails (5-10 examples)
   - Recipient count and segments
   - Estimated send time
   - Compliance checklist
2. Requires manual review and approval
3. Implements 1-hour delay for final changes

**Approval Methods:**
- Web dashboard campaign preview
- Test email to approvers
- CLI command: `leadfactory approve-campaign <campaign-id>`

### 3. Cost Threshold Alerts (P0-010)

**When Triggered:**
- When daily spend exceeds 80% of budget
- When any single operation costs > $50
- When projected monthly cost exceeds budget

**Process:**
1. System pauses high-cost operations
2. Sends immediate alert with:
   - Current spend details
   - Cost breakdown by service
   - Projection for remaining period
3. Requires acknowledgment to continue

**Response Options:**
- Increase budget limit
- Pause specific services
- Continue with current limits
- Implement stricter controls

### 4. AI Model Upgrades (P1-024)

**When Triggered:**
- Before switching from gpt-4o-mini to gpt-4
- When enabling experimental AI features
- When AI-generated content differs significantly from baseline

**Process:**
1. System runs A/B comparison:
   - Current model output
   - New model output
   - Cost difference
   - Quality metrics
2. Generates comparison report
3. Requires explicit approval for production use

**Approval Methods:**
- Side-by-side comparison in dashboard
- Detailed metrics report
- Gradual rollout approval (10% → 50% → 100%)

## Implementation Details

### Feature Flag Control
```python
# All HITL processes controlled by feature flag
ENABLE_HUMAN_IN_THE_LOOP = os.getenv('ENABLE_HUMAN_IN_THE_LOOP', 'true')

# Individual checkpoint flags
HITL_DATA_PURCHASE = os.getenv('HITL_DATA_PURCHASE', 'true')
HITL_EMAIL_CAMPAIGN = os.getenv('HITL_EMAIL_CAMPAIGN', 'true')
HITL_COST_THRESHOLD = os.getenv('HITL_COST_THRESHOLD', 'true')
HITL_AI_UPGRADE = os.getenv('HITL_AI_UPGRADE', 'true')
```

### Notification Channels
1. **Email** (primary)
   - Sent to designated approvers
   - Includes secure approval links
   - 24-hour expiration

2. **Dashboard Queue**
   - Real-time pending approvals
   - Detailed request information
   - Audit trail of decisions

3. **CLI Interface**
   - For automated workflows
   - Scriptable approvals
   - Bulk operations support

### Timeout Handling
- Default timeout: 24 hours
- Configurable per checkpoint type
- Automatic escalation after 12 hours
- Safe default action (usually "deny") on timeout

### Audit Trail
All HITL decisions are logged with:
- Timestamp
- Approver identity
- Decision (approve/reject/timeout)
- Reason/comments
- System state snapshot

## Development Mode

In development (USE_STUBS=true), HITL checkpoints:
- Log decisions but don't block
- Auto-approve after 5 seconds
- Generate mock approval emails
- Display console notifications

## Production Safeguards

1. **Multiple Approvers**: Critical operations require 2+ approvals
2. **Role-Based Access**: Only designated roles can approve
3. **Rate Limiting**: Prevent approval fatigue
4. **Revocation**: Approved actions can be cancelled within 5 minutes
5. **Monitoring**: All HITL metrics tracked in Datadog

## Testing HITL Processes

```bash
# Test HITL workflow
pytest tests/test_hitl_process.py

# Simulate approval flow
python scripts/test_hitl_simulation.py

# Check HITL configuration
leadfactory hitl-status
```

## Troubleshooting

### Common Issues

1. **Approvals Not Received**
   - Check email configuration
   - Verify approver list is current
   - Check spam folders

2. **Timeout Errors**
   - Review timeout settings
   - Check system clock sync
   - Verify notification delivery

3. **Approval Loop**
   - Check decision persistence
   - Verify state management
   - Review retry logic

### Emergency Override

In production emergencies, HITL can be temporarily disabled:
```bash
# Disable for 1 hour with audit log
leadfactory hitl-override --duration=1h --reason="Emergency fix for X"
```

## Best Practices

1. **Keep Approver List Updated**: Review monthly
2. **Test Approval Flows**: Include in release testing
3. **Monitor Response Times**: Track approval latency
4. **Document Decisions**: Require reason for rejections
5. **Regular Audits**: Review HITL logs quarterly

## Future Enhancements

- Mobile app for approvals
- Slack/Teams integration
- ML-based auto-approval for low-risk operations
- Approval delegation workflows
- Enhanced analytics dashboard