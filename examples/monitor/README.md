# Monitoring the runner with the CloudWatch agent

An example of monitoring the runner with the CloudWatch agent.

## 1. Install and set up the CloudWatch agent

Set up the agent by following:
https://repost.aws/knowledge-center/cloudwatch-on-premises-temp-credentials

The host runs as a Systems Manager hybrid managed node, so the agent uses short lived credentials.

### Preparation: Command examples

Please change the role name.

Create role:

```bash
aws iam create-role \
  --role-name openeval-runner-ssm-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ssm.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
```

```bash
aws iam attach-role-policy \
  --role-name openeval-runner-ssm-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
```

```bash
aws iam attach-role-policy \
  --role-name openeval-runner-ssm-role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy
```

Confirm:

```console
$ aws iam list-attached-role-policies --role-name openeval-runner-ssm-role
{
    "AttachedPolicies": [
        {
            "PolicyName": "CloudWatchAgentServerPolicy",
            "PolicyArn": "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
        },
        {
            "PolicyName": "AmazonSSMManagedInstanceCore",
            "PolicyArn": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
        }
    ]
}
```

Activation:

Keep a note of the output.

```console
$ aws ssm create-activation \
  --iam-role openeval-runner-ssm-role \
  --registration-limit 1 \
  --default-instance-name openeval-runner \
  --region ap-northeast-1
{
    "ActivationId": "xxx",
    "ActivationCode": "yyy"
}
```

### Install the SSM Agent: Command examples

```bash
curl https://amazon-ssm-ap-northeast-1.s3.ap-northeast-1.amazonaws.com/latest/debian_amd64/ssm-setup-cli -o /tmp/ssm-setup-cli
chmod 755 /tmp/ssm-setup-cli
```

Specify the ID and code you noted down.

```bash
sudo /tmp/ssm-setup-cli -register \
  -activation-id "xxx" \
  -activation-code "yyy" \
  -region ap-northeast-1
```

Confirm:

```console
$ systemctl status amazon-ssm-agent
● amazon-ssm-agent.service - amazon-ssm-agent
     Loaded: loaded (/usr/lib/systemd/system/amazon-ssm-agent.service; enabled; preset: enabled)
    Drop-In: /run/systemd/system/service.d
             └─zzz-lxc-service.conf
     Active: active (running) since Wed 2026-07-29 02:54:53 UTC; 2min 27s ago
   Main PID: 2162 (amazon-ssm-agen)
      Tasks: 36 (limit: 76769)
     Memory: 27.4M ()
     CGroup: /system.slice/amazon-ssm-agent.service
             ├─2162 /usr/bin/amazon-ssm-agent
             └─2185 /usr/bin/ssm-agent-worker

...
```

```console
$ aws ssm describe-instance-information --region ap-northeast-1
{
    "InstanceInformationList": [
        {
            "InstanceId": "mi-nnn",
            "PingStatus": "Online",
            "LastPingDateTime": "2026-07-29T03:01:15.348000+00:00",
            "AgentVersion": "3.3.4121.0",
            "IsLatestVersion": false,
            "PlatformType": "Linux",
            "PlatformName": "Ubuntu",
            "PlatformVersion": "24.04",
            "ActivationId": "xxx",
            "IamRole": "openeval-runner-ssm-role",
            "RegistrationDate": "2026-07-29T02:54:53.664000+00:00",
            "ResourceType": "ManagedInstance",
            "Name": "openeval-runner",
            "IPAddress": "x.x.x.x",
            "ComputerName": "hostname",
            "SourceId": "mi-mmm",
            "SourceType": "AWS::SSM::ManagedInstance"
        }
    ]
}
```

### Install the CloudWatch Agent: Command examples

```bash
curl https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb \
  -o /tmp/amazon-cloudwatch-agent.deb
sudo dpkg -i /tmp/amazon-cloudwatch-agent.deb
```

## 2. Configure and start the agent

https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/start-CloudWatch-Agent-on-premise-SSM-onprem.html

`/opt/aws/amazon-cloudwatch-agent/etc/common-config.toml`:

```toml
[credentials]
  shared_credential_profile = "default"
  shared_credential_file = "/root/.aws/credentials"
```

`/tmp/amazon-cloudwatch-agent.json`:

```json
{
  "agent": {
    "region": "ap-northeast-1"
  },
  "metrics": {
    "namespace": "OpenEvalRunner",
    "metrics_collected": {
      "procstat": [
        {
          "pattern": "openeval_runner\\.runner",
          "measurement": ["pid_count"],
          "metrics_collection_interval": 60
        }
      ],
      "disk": {
        "resources": ["/"],
        "measurement": ["used_percent"],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/syslog",
            "log_group_name": "/openeval-runner/syslog",
            "log_stream_name": "{hostname}",
            "retention_in_days": 7
          }
        ]
      }
    }
  }
}
```

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m onPremise -s \
  -c file:/tmp/amazon-cloudwatch-agent.json
```

Confirm:

```console
$ /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a status
{
  "status": "running",
  "starttime": "2026-07-29T03:35:25+00:00",
  "configstatus": "configured",
  "version": "1.300069.0b1529"
}
```

Log: `/opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log`

## 3. Alarms

### Create a topic

```bash
aws sns create-topic --name openeval-runner-alerts \
  --region ap-northeast-1
```

Note the ARN.

```bash
aws sns subscribe \
  --topic-arn <topic-arn> \
  --protocol email \
  --notification-endpoint <email@address> \
  --region ap-northeast-1
```

Confirm your subscription via email.

### Create a metric filter

```bash
aws logs put-metric-filter \
  --log-group-name /openeval-runner/syslog \
  --filter-name openeval-cell-not-ready \
  --filter-pattern '"paused: cell is not ready"' \
  --metric-transformations \
      metricName=CellNotReady,metricNamespace=OpenEvalRunner,metricValue=1,defaultValue=0 \
  --region ap-northeast-1
```

### Create an alarm: runner process

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name openeval-runner-down \
  --alarm-description "openeval runner process is not running" \
  --namespace OpenEvalRunner \
  --metric-name procstat_lookup_pid_count \
  --dimensions Name=host,Value=<hostname> 'Name=pattern,Value=openeval_runner\.runner' Name=pid_finder,Value=native \
  --statistic Maximum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --treat-missing-data breaching \
  --alarm-actions <topic-arn> \
  --region ap-northeast-1
```

### Create an alarm: cell not ready

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name openeval-cell-not-ready \
  --alarm-description "openeval runner reported the cell is not ready" \
  --namespace OpenEvalRunner \
  --metric-name CellNotReady \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions <topic-arn> \
  --region ap-northeast-1
```
