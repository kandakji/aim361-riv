
# Welcome to your CDK Python project!

This is a blank project for CDK development with Python.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!

## Tasks

### Create the input S3 Bucket

```python
input_bucket = s3.Bucket(
    self,
    "input-bucket",
    enforce_ssl=True,
    encryption=s3.BucketEncryption.S3_MANAGED,
    event_bridge_enabled=True,
    removal_policy=RemovalPolicy.DESTROY,
)
output_bucket = s3.Bucket(
    self,
    "output-bucket",
    enforce_ssl=True,
    encryption=s3.BucketEncryption.S3_MANAGED,
    removal_policy=RemovalPolicy.DESTROY,
)
```

### Create a Step Function & Trigger

```python
s3ToStepfunction = S3ToStepfunctions(
            self,
            "step-function",
            state_machine_props=sfn.StateMachineProps(
                definition=bedrock_task, tracing_enabled=True
            ),
            existing_bucket_obj=input_bucket,
        )
```

#### Create Step calling Bedrock

```python
bedrock_lambda = lambda_.Function(
            self,
            "bedrock-lambda",
            handler="lambda_function.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("lambdas/bedrock"),
            environment={"GUARDRAIL": "RIV-test", "modelId": model.model_id},
            tracing=lambda_.Tracing.ACTIVE,
        )

bedrock_lambda.role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
)

bedrock_task = tasks.LambdaInvoke(
    self,
    "invoke-bedrock-lambda",
    lambda_function=bedrock_lambda,
    payload=sfn.TaskInput.from_object({"body": sfn.JsonPath.entire_payload}),
    payload_response_only=True,
    result_path="$.Payload",
)
```