# AWS Lambda function for setting up a traffic mirror session

The function is intended to be triggered by CloudWatch events.

Example event pattern:

```
{
  "detail-type": [
    "EC2 Instance State-change Notification"
  ],
  "detail": {
    "state": [
      "running"
    ]
  },
  "source": [
    "aws.ec2"
  ]
}
```

## Required environment variables

- MIRROR_TARGET_ID
- MIRROR_FILTER_ID

## Optional environment variables

- MIRROR_SKIP_TAGS (should be used to exclude some instances from mirroring, example: "instance_key_with_exact_value=value,key_with_empty_value=,key_present")

## Test

```
import lambda_function

sample_event = {
    "source": [
        "aws.ec2"
    ],
    "detail-type": [
        "EC2 Instance State-change Notification"
    ],
    "detail": {
        "state": [
            "running"
        ],
        "instance-id": "i-060332d6730812468"
    }
}

lambda_handler(sample_event, None)

```

## Troubleshooting

Set `LAMBDA_LOG_LEVEL` env variable to required log level, eg. `INFO`
