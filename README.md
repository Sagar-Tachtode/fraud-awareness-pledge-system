# Pledge Certificate Generation Project

A comprehensive AWS Lambda-based solution for dynamically generating personalized pledge certificates for Edelweiss Life Insurance. The system generates professional PDF certificates with employee names, saves them to S3, and tracks all generated certificates in DynamoDB.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup Guide](#setup-guide)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [File Structure](#file-structure)
- [Security](#security)
- [Contributing](#contributing)

---

## 🎯 Overview

This project automates the generation of "Code of Honor" pledge certificates for Edelweiss Life Insurance employees. The application:

- **Generates personalized PDF certificates** with employee names dynamically overlaid
- **Stores certificates** in AWS S3 for easy retrieval
- **Tracks all certificates** in DynamoDB with metadata
- **Runs on AWS Lambda** for serverless, scalable deployment
- **Integrates with employee data** from CSV files stored in S3

### Key Features

✅ Dynamic name positioning on certificates  
✅ Professional certificate design with Edelweiss branding  
✅ Automatic S3 storage with organized folder structure  
✅ DynamoDB tracking of all generated certificates  
✅ Comprehensive logging and error handling  
✅ Scalable serverless architecture  

---

## 🏗️ Architecture

```
Employee Request
    ↓
Lambda Function
    ├─→ Generate PDF (certificate template + employee name)
    ├─→ Upload to S3 (certificates/generated/)
    └─→ Save metadata to DynamoDB (Employees_List table)
    ↓
Response (Success/Error)
```

### AWS Services Used

- **AWS Lambda**: Serverless compute for certificate generation
- **Amazon S3**: Storage for certificate templates and generated PDFs
- **Amazon DynamoDB**: Database for tracking certificates and employee data
- **IAM**: Access control and permissions

---

## 📦 Prerequisites

Before setting up this project, ensure you have:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured on your machine
3. **Python 3.9+** runtime
4. **Pillow (PIL)** library for image processing
5. **boto3** Python library
6. **Certificate template image** (JPEG format) uploaded to S3

### Required AWS Services

- S3 bucket: `pledge-certificate-generation-project`
- Lambda function with sufficient timeout (minimum 30 seconds)
- DynamoDB table: `Employees_List`
- IAM role with appropriate permissions

---

## 🚀 Setup Guide

### Step 1: Create S3 Bucket

```bash
aws s3 mb s3://pledge-certificate-generation-project --region ap-south-1
```

### Step 2: Upload Certificate Template

Upload your certificate template image to:
```
s3://pledge-certificate-generation-project/FAW_ Certificate_ Without name & download.jpeg
```

**Template Specifications:**
- Format: JPEG or PNG
- Resolution: 800x600px (minimum)
- Contains: Edelweiss branding, pledge text, all design elements
- Text placement: Name should be positioned to the right of "#BeAlertStaySecure"

### Step 3: Create DynamoDB Table

Using AWS Console:

1. Go to **DynamoDB** → **Tables** → **Create table**
2. **Table name**: `Employees_List`
3. **Partition key**: `employee_id` (String)
4. **Billing mode**: On-demand (PAY_PER_REQUEST)
5. Click **Create table**

Alternatively, using AWS CLI:

```bash
aws dynamodb create-table \
  --table-name Employees_List \
  --attribute-definitions AttributeName=employee_id,AttributeType=S \
  --key-schema AttributeName=employee_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### Step 4: Create Lambda Function

1. Go to **AWS Lambda** → **Create function**
2. **Function name**: `pledge-certificate-generator`
3. **Runtime**: Python 3.9 or higher
4. **Handler**: `lambda_function.lambda_handler`

### Step 5: Add Pillow Lambda Layer

The Lambda function requires Pillow (PIL) for image processing.

**Option A: Using pre-built layer**

Create a ZIP with Pillow:

```bash
mkdir python
pip install Pillow -t python/
zip -r pillow-layer.zip python/
```

Upload to Lambda as a layer:

```bash
aws lambda publish-layer-version \
  --layer-name pillow-layer \
  --zip-file fileb://pillow-layer.zip \
  --compatible-runtimes python3.9 \
  --region ap-south-1
```

**Option B: Upload layer to Lambda**

1. Go to Lambda function → **Layers** → **Add layer**
2. Upload the PIL/Pillow layer ZIP file

### Step 6: Deploy Lambda Function Code

Deploy the complete Lambda function code (see Configuration section).

### Step 7: Configure IAM Permissions

Add this policy to your Lambda execution role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::pledge-certificate-generation-project/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:ap-south-1:*:table/Employees_List"
        }
    ]
}
```

---

## ⚙️ Configuration

### Lambda Function Code

```python
import boto3
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Initialize clients at the module level
s3_client = boto3.client('s3', region_name='ap-south-1')
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
table = dynamodb.Table('Employees_List')

print("✓ DynamoDB table initialized: Employees_List")

def generate_certificate_pdf(employee_name):
    """Generate certificate with dynamic employee name"""
    try:
        response = s3_client.get_object(
            Bucket='pledge-certificate-generation-project',
            Key='FAW_ Certificate_ Without name & download.jpeg'
        )
        
        template_image = Image.open(BytesIO(response['Body'].read()))
        draw = ImageDraw.Draw(template_image)
        
        # Load font - try multiple options for Lambda compatibility
        try:
            name_font = ImageFont.truetype("/var/task/arial.ttf", 28)
        except:
            try:
                name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            except:
                name_font = ImageFont.load_default()
        
        # Position name on certificate
        x_position = int(template_image.width * 0.52)  # 52% from left
        y_position = int(template_image.height * 0.65)  # 65% from top
        text_color = (30, 70, 130)  # Dark blue
        
        # Draw employee name
        draw.text(
            (x_position, y_position),
            employee_name.upper(),
            fill=text_color,
            font=name_font,
            anchor="lm"
        )
        
        # Convert to PDF
        buffer = BytesIO()
        template_image_rgb = template_image.convert('RGB')
        template_image_rgb.save(buffer, format='PDF')
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except Exception as e:
        print(f"Error generating certificate: {str(e)}")
        raise

def save_to_dynamodb(employee_id, employee_name, certificate_key):
    """Save employee certificate details to DynamoDB"""
    try:
        print(f"Attempting to save to DynamoDB table: {table.table_name}")
        
        table.put_item(
            Item={
                'employee_id': employee_id,
                'employee_name': employee_name,
                'certificate_key': certificate_key,
                'generated_date': datetime.now().isoformat(),
                'status': 'Certificate Generated'
            }
        )
        print(f"✓ Successfully saved to DynamoDB: {employee_id} - {employee_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error saving to DynamoDB: {str(e)}")
        raise

def lambda_handler(event, context):
    """Main Lambda handler for certificate generation"""
    
    try:
        body = json.loads(event.get('body', '{}'))
        employee_id = body.get('employee_id')
        employee_name = body.get('employee_name')
        
        # Validate input
        if not employee_id or not employee_name:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'message': 'employee_id and employee_name are required'
                })
            }
        
        # Step 1: Generate certificate PDF
        print(f"Step 1: Generating certificate for {employee_name}...")
        pdf_bytes = generate_certificate_pdf(employee_name)
        
        # Step 2: Save certificate to S3
        cert_key = f"certificates/generated/{employee_id}_{employee_name.replace(' ', '_')}.pdf"
        s3_client.put_object(
            Bucket='pledge-certificate-generation-project',
            Key=cert_key,
            Body=pdf_bytes,
            ContentType='application/pdf'
        )
        print(f"✓ Certificate saved to S3: {cert_key}")
        
        # Step 3: Save employee details to DynamoDB
        print("Step 3: Saving to DynamoDB...")
        save_to_dynamodb(employee_id, employee_name, cert_key)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': 'Certificate generated and details saved to DynamoDB',
                'employee_id': employee_id,
                'employee_name': employee_name,
                'certificate_key': cert_key
            })
        }
        
    except Exception as e:
        print(f"✗ Lambda Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f'Internal server error: {str(e)}'
            })
        }
```

### Configuration Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| AWS Region | `ap-south-1` | Change if using different region |
| S3 Bucket | `pledge-certificate-generation-project` | Must exist and have certificate template |
| DynamoDB Table | `Employees_List` | Table with `employee_id` as partition key |
| Font Size | 28 | Adjust based on certificate template |
| X Position | 0.52 (52%) | Horizontal placement of name |
| Y Position | 0.65 (65%) | Vertical placement of name |
| Text Color | (30, 70, 130) | RGB values for dark blue |

---

## 💻 Usage

### API Endpoint (via API Gateway)

**Endpoint**: `POST /certificates`

**Request Body**:
```json
{
    "employee_id": "EMP001",
    "employee_name": "Amit Patel"
}
```

**Success Response** (HTTP 200):
```json
{
    "success": true,
    "message": "Certificate generated and details saved to DynamoDB",
    "employee_id": "EMP001",
    "employee_name": "Amit Patel",
    "certificate_key": "certificates/generated/EMP001_Amit_Patel.pdf"
}
```

**Error Response** (HTTP 400/500):
```json
{
    "success": false,
    "message": "Error description here"
}
```

### Direct Lambda Invocation

```bash
aws lambda invoke \
  --function-name pledge-certificate-generator \
  --payload '{"body": "{\"employee_id\": \"EMP001\", \"employee_name\": \"Amit Patel\"}"}' \
  --region ap-south-1 \
  response.json

cat response.json
```

### Python Example

```python
import boto3
import json

lambda_client = boto3.client('lambda', region_name='ap-south-1')

payload = {
    "body": json.dumps({
        "employee_id": "EMP001",
        "employee_name": "Amit Patel"
    })
}

response = lambda_client.invoke(
    FunctionName='pledge-certificate-generator',
    InvocationType='RequestResponse',
    Payload=json.dumps(payload)
)

result = json.loads(response['Payload'].read().decode())
print(result)
```

---

## 📖 API Reference

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `employee_id` | String | Yes | Unique employee identifier (e.g., EMP001) |
| `employee_name` | String | Yes | Full name of employee to display on certificate |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | Boolean | Operation success status |
| `message` | String | Success or error message |
| `employee_id` | String | Employee ID from request |
| `employee_name` | String | Employee name from request |
| `certificate_key` | String | S3 path to generated PDF |

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Certificate generated successfully |
| 400 | Missing or invalid parameters |
| 404 | Employee not found in DynamoDB |
| 500 | Server error during processing |

---

## 🔍 Troubleshooting

### Error: "Pillow module not found"

**Solution**: Add Pillow Lambda layer

```bash
pip install Pillow -t python/
zip -r pillow-layer.zip python/
aws lambda publish-layer-version \
  --layer-name pillow-layer \
  --zip-file fileb://pillow-layer.zip \
  --compatible-runtimes python3.9
```

### Error: "name 'table' is not defined"

**Cause**: DynamoDB client not initialized at module level  
**Solution**: Ensure boto3 initialization is at the top of the Lambda code, outside functions

### Error: "Access Denied" to S3 or DynamoDB

**Solution**: Verify IAM role has correct permissions:

```bash
aws iam get-role-policy \
  --role-name lambda-execution-role \
  --policy-name certificate-generation-policy
```

### Certificate Name Position is Wrong

**Solution**: Adjust position parameters in the code:

```python
x_position = int(template_image.width * 0.52)  # Change 0.52 for horizontal adjustment
y_position = int(template_image.height * 0.65)  # Change 0.65 for vertical adjustment
```

- Decrease percentage to move left/up
- Increase percentage to move right/down

### Lambda Timeout

**Solution**: Increase timeout in Lambda configuration:

1. Go to **Lambda** → **Function** → **Configuration** → **General configuration**
2. Increase **Timeout** to 60 seconds

### Font Not Found

**Solution**: The Lambda environment may not have custom fonts. The code uses fallback fonts:

1. DejaVuSans-Bold (usually available)
2. Default system font
3. Built-in Pillow font

To use custom fonts, upload them to a Lambda layer.

---

## 📁 File Structure

```
pledge-certificate-generation-project/
├── README.md                                    # This file
├── lambda_function.py                           # Main Lambda handler
├── requirements.txt                             # Python dependencies
├── s3/
│   ├── FAW_Certificate_Without_name.jpeg       # Certificate template
│   └── certificates/
│       └── generated/
│           ├── EMP001_Amit_Patel.pdf
│           ├── EMP002_Jane_Smith.pdf
│           └── ...
└── dynamodb/
    └── Employees_List/
        ├── EMP001 | Amit Patel | cert_key | timestamp
        ├── EMP002 | Jane Smith | cert_key | timestamp
        └── ...
```

### S3 Bucket Structure

```
s3://pledge-certificate-generation-project/
├── FAW_Certificate_Without_name & download.jpeg
└── certificates/
    └── generated/
        ├── EMP001_Amit_Patel.pdf
        ├── EMP002_Jane_Smith.pdf
        └── EMP003_Rajesh_Kumar.pdf
```

### DynamoDB Table Schema

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `employee_id` | String | HASH (Partition) | Unique employee identifier |
| `employee_name` | String | - | Full name of employee |
| `certificate_key` | String | - | S3 path to PDF file |
| `generated_date` | String | - | ISO timestamp of generation |
| `status` | String | - | Current status (e.g., "Certificate Generated") |

---

## 🔐 Security

### Best Practices

1. **IAM Permissions**: Use least privilege principle
   - Only grant `s3:GetObject` for template
   - Only grant `s3:PutObject` for generated certificates
   - Only grant `dynamodb:PutItem` for table writes

2. **S3 Bucket Security**
   - Enable versioning
   - Enable server-side encryption
   - Block public access
   - Set appropriate lifecycle policies

3. **DynamoDB Security**
   - Enable encryption at rest
   - Use VPC endpoints if needed
   - Monitor access with CloudTrail

4. **Lambda Security**
   - Use VPC if accessing private resources
   - Enable X-Ray tracing for monitoring
   - Set appropriate timeout values
   - Enable detailed CloudWatch logging

### Encryption

```bash
# Enable S3 encryption
aws s3api put-bucket-encryption \
  --bucket pledge-certificate-generation-project \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

---

## 📊 Monitoring

### CloudWatch Logs

View Lambda execution logs:

```bash
aws logs tail /aws/lambda/pledge-certificate-generator --follow
```

### CloudWatch Metrics

Monitor key metrics:

- **Invocations**: Total function calls
- **Duration**: Average execution time
- **Errors**: Failed executions
- **Throttles**: Rate limit hits

### X-Ray Tracing

Enable X-Ray for detailed performance insights:

```bash
aws lambda update-function-configuration \
  --function-name pledge-certificate-generator \
  --tracing-config Mode=Active
```

---

## 🚀 Performance Optimization

1. **Memory Configuration**: Set to 512 MB or higher
2. **Provisioned Concurrency**: For high-volume workloads
3. **S3 Optimization**: Use multipart upload for large files
4. **DynamoDB**: Use on-demand billing for variable workloads

---

## 📝 License

This project is proprietary to Edelweiss Life Insurance.

---

## 👥 Support & Contributing

For issues, enhancements, or questions:

1. Create an issue in the project repository
2. Document the error and steps to reproduce
3. Include relevant logs and configuration details
4. Contact the development team for urgent issues

---

## 📅 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Nov 2025 | Initial release with certificate generation, S3 storage, and DynamoDB tracking |

---

**Last Updated**: November 11, 2025