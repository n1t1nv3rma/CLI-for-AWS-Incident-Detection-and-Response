# Update Workload

The `update-workload` command allows you to request updates to existing IDR workload configurations. This creates a support case routed to the IDR team for processing.

## Command

```
awsidr update-workload [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-r, --resume` | Resume a paused session |
| `--config` | Path to JSON config file for non-interactive mode |

## Update Types

### 1. Contacts/Escalation

Update primary and escalation contact information for an existing workload.

**Information collected:**
- Primary contact: name, email, phone (optional)
- Escalation contact: name, email, phone (optional)

### 2. Alarms

Add new alarms to an existing workload.

**CloudWatch Alarms - Input Methods:**
- Find alarms by tags (with region selection)
- Upload a text file with ARNs
- Enter ARNs manually

**APM Alarms:**
- EventBridge CustomEventBus ARN
- Alert identifiers (comma-separated)

## Interactive Session Flow

```
Step 1/4: Enter Workload Name
Step 2/4: Select Update Type (Contacts or Alarms)
Step 3/4: Enter Update Details
Step 4/4: Review and Submit
```

## Example Usage

### Interactive Mode

```bash
# Start new update request
awsidr update-workload

# Resume paused session
awsidr update-workload --resume
```

### Non-Interactive Mode

```bash
# Update contacts using config file
awsidr update-workload --config update-contacts.json

# Update alarms using config file
awsidr update-workload --config update-alarms.json
```

## Session Examples

### Contacts/Escalation Update

```
Step 1/4: Enter Workload Name
→ Enter the workload name: Test WL

✅ Workload: Test WL

Step 2/4: Select Update Type

Update Type Selection
Select what to update:
──────────────────────

Available update options:
  1. Contacts/Escalation
  2. Alarms
→ Enter your choice (1-2) : 1

✅ Update type: Contacts/Escalation

Step 3/4: Enter Update Details

📞 Collecting updated primary and escalation contact information

📞 Primary Incident Contact Information
──────────────────────────────────────

Primary incident contact serves as the initial point of contact for AWS IDR incident and alarm notifications.
→ Primary contact name: Test PC
→ Primary contact email: pc@example.com

📱 Format examples: +1-555-123-4567, (555) 123-4567, +44 20 7946 0958
→ Primary contact phone (optional):

📞 Escalation Incident Contact Information
─────────────────────────────────────────

Escalation contact will be contacted if primary contact is unreachable during an incident.
→ Escalation contact name: Test EC
→ Escalation contact email: ec@example.com

📱 Format examples: +1-555-123-4567, (555) 123-4567, +44 20 7946 0958
→ Escalation contact phone (optional):

✅ Alarm contact information collected

Step 4/4: Review and Submit

Review Update Request
─────────────────────
╭─────────────────────────── Alarm Contact Information Summary ───────────────────────────╮
│ Primary Name: Test PC                                                                   │
│ Primary Email: pc@example.com                                                           │
│ Primary Phone: (not provided)                                                           │
│ Escalation Name: Test EC                                                                │
│ Escalation Email: ec@example.com                                                        │
│ Escalation Phone: (not provided)                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
→ Would you like to submit this update request? (y):

📤 Submitting update request...
╭──────────────────────────────── 📋 Support Case Created ────────────────────────────────╮
│ Case ID: 177065950600439                                                                │
│ Status: unassigned                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────╯

 ✅ IDR Workload Onboarding request submitted
```

### Alarms Update - CloudWatch (by tags)

```
Step 1/4: Enter Workload Name
→ Enter the workload name: Test

✅ Workload: Test

Step 2/4: Select Update Type

Update Type Selection
Select what to update:
──────────────────────

Available update options:
  1. Contacts/Escalation
  2. Alarms
→ Enter your choice (1-2) : 2

✅ Update type: Alarms

Step 3/4: Enter Update Details

🔔 What type of alarms would you like to add?

Select alarm type:
  1. CloudWatch Alarms
  2. APM Alarms (eg. Datadog, New Relic etc.)
→ Enter your choice (1-2) : 1

How would you like to provide alarm ARNs?

Select input method:
  1. Find alarms by tags
  2. Upload a text file with ARNs
  3. Enter ARNs manually
→ Enter your choice (1-3) : 1

📍 Select regions to search for alarms
→ Regions (comma-separated): us-east-1

How would you like to specify tags?:
  1. Single tag (key and value separately)
  2. Multiple tags (key1=value1,key2=value1|value2)
→ Enter your choice (1-2) : 1
→ Tag key (Application) : Owner
→ Tag value: CLI
→ Would you like to proceed with Owner=['CLI']? (y):

🔍 Searching for CloudWatch alarms...

Searching for CloudWatch alarms in region: us-east-1

✅ Found 4 CloudWatch alarms in region: us-east-1

✅ Found 4 alarm(s) matching tag criteria

Step 4/4: Review and Submit

Review Update Request
─────────────────────
╭─────────────────────────────── CloudWatch Alarms to Add ────────────────────────────────╮
│ Count: 4                                                                                │
│ ARNs: ['arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm-1',                   │
│ 'arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm-2',                          │
│ 'arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm-3',                          │
│ 'arn:aws:cloudwatch:us-east-1:123456789012:alarm:TestAlarm-4']                          │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
→ Would you like to submit this update request? (y):

📤 Submitting update request...
╭──────────────────────────────── 📋 Support Case Created ────────────────────────────────╮
│ Case ID: 177074028900628                                                                │
│ Status: unassigned                                                                      │
╰─────────────────────────────────────────────────────────────────────────────────────────╯

 ✅ IDR Workload Onboarding request submitted
```

### Alarms Update - APM

```
🔔 What type of alarms would you like to add?

Select alarm type:
  1. CloudWatch Alarms
  2. APM Alarms (eg. Datadog, New Relic etc.)
→ Enter your choice (1-2) : 2

📡 APM Alarm Configuration

📍 Enter the region where your CustomEventBus is deployed
→ Region: us-east-1

Enter the EventBridge CustomEventBus ARN from your APM CloudFormation stack
→ EventBridge event bus ARN: arn:aws:events:us-east-1:123456789012:event-bus/idr-custom-bus

Enter comma-separated alert identifiers that your APM sends
→ Alert identifiers: error-counts,cpu-utilization,latency

✅ Configured 3 alert identifier(s)
```

## What Happens After Submission

1. A support case is created with your update request
2. The case is routed to the IDR team via CTI: Technical support | Incident Detection and Response | Workload Change Request
3. For contacts updates: Contact information is included in the support case body
4. For alarm updates: A JSON attachment is included
5. The IDR team processes your request and updates your workload configuration

## See Also

- [Workload Registration](workload-registration.md)
- [Alarm Ingestion](alarm-ingestion.md)
- [Unattended Mode](../unattended-mode.md)
- [Workflows](../workflows.md)
- [FAQ](../faq.md)
