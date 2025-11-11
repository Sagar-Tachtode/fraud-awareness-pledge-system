import json
import boto3
import csv
import os
from datetime import datetime
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
import uuid
import base64

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'pledge-certificate-generation-project')
CSV_KEY = os.environ.get('CSV_KEY', 'employees.csv')
employee_table = dynamodb.Table('Employees_List')
print("✓ DynamoDB table initialized: Employees_List")

# In-memory cache
employee_cache = {'data': None, 'timestamp': None}
CACHE_TTL = 300

def load_employees_from_s3():
    """Load employee data from S3 CSV with caching"""
    global employee_cache
    current_time = datetime.now().timestamp()
    
    if employee_cache['data'] and employee_cache['timestamp']:
        if current_time - employee_cache['timestamp'] < CACHE_TTL:
            print(f"✓ Using cached employee data ({len(employee_cache['data'])} employees)")
            return employee_cache['data']
    
    print(f"Loading employees from S3: s3://{BUCKET_NAME}/{CSV_KEY}")
    
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=CSV_KEY)
        csv_content = response['Body'].read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_content))
        employees = {row['employee_id']: row for row in csv_reader}
        employee_cache['data'] = employees
        employee_cache['timestamp'] = current_time
        print(f"✓ Loaded {len(employees)} employees from S3")
        return employees
    except Exception as e:
        print(f"✗ Error loading employees: {str(e)}")
        raise

#####################################################################################################################
import boto3
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

s3_client = boto3.client('s3')

def generate_certificate_pdf(employee_name):
    """Generate certificate with dynamic employee name"""
    
    try:
        # Download template from S3
        response = s3_client.get_object(
            Bucket='pledge-certificate-generation-project',
            Key='FAW_ Certificate_ Without name & download.jpeg'
        )
        
        # Open image from S3
        template_image = Image.open(BytesIO(response['Body'].read()))
        draw = ImageDraw.Draw(template_image)
        
        # Load font
        try:
            name_font = ImageFont.truetype("/var/task/arial.ttf", 20)
        except:
            try:
                name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            except:
                name_font = ImageFont.load_default()
        
        # Position: to the right of #BeAlertStaySecure
        x_position = int(template_image.width * 0.52)   ### change from 0.58 to 0.52 to move left
        y_position = int(template_image.height * 0.70)  ## changed from 0.58 to 0.70 to move down
        
        # Text color: dark blue
        text_color = (30, 70, 130)
        
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

#####################################################################################################################

def save_to_dynamodb(employee_id, employee_name, certificate_key):
    """Save employee details to DynamoDB after certificate is saved"""
    try:
        employee_table.put_item(
            Item={
                'employee_id': employee_id,
                'employee_name': employee_name,
                'certificate_key': certificate_key,
                'generated_date': datetime.now().isoformat(),
                'status': 'Certificate Generated'
            }
        )
        print(f"✓ Saved to DynamoDB: {employee_id} - {employee_name}")
        return True
        
    except Exception as e:
        print(f"Error saving to DynamoDB: {str(e)}")
        raise

#####################################################################################################################

def lambda_handler(event, context):
    """Main Lambda handler - CORS handled by Function URL"""
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        employee_id = body.get('employee_id')
        pledge_accepted = body.get('pledge_accepted', False)
        
        # Validation
        if not employee_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},  # Only Content-Type
                'body': json.dumps({'success': False, 'message': 'Employee ID is required'})
            }
        
        if not pledge_accepted:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': 'Pledge must be accepted'})
            }
        
        # Load employee data
        print(f"Looking up employee: {employee_id}")
        employees = load_employees_from_s3()
        
        if employee_id not in employees:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': f'Employee {employee_id} not found'})
            }
        
        employee = employees[employee_id]
        employee_name = employee['employee_name']
        department = employee.get('department', 'N/A')
        designation = employee.get('designation', 'N/A')
        
          # Step 1: Generate certificate PDF
        date_str = datetime.now().strftime("%B %d, %Y")
        pdf_bytes = generate_certificate_pdf(employee_name)
        
        # Convert to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Generate pledge ID
        pledge_id = str(uuid.uuid4())
        
        # Upload to S3
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cert_key = f"certificates/{employee_id}_{timestamp}.pdf"
        
        # Step 2: Save certificate to S3:
        try:
            s3_client.put_object(Bucket=BUCKET_NAME,
                                 Key=cert_key,
                                 Body=pdf_bytes,
                                 ContentType='application/pdf'
                                )
            print(f"✓ Certificate uploaded to S3: {cert_key}")
        except Exception as e:
            print(f"⚠ S3 upload failed (non-critical): {str(e)}")
        
        print(f"✓ Pledge processed successfully for {employee_id}")

        # Step 3: Save employee details to DynamoDB:
        save_to_dynamodb(employee_id, employee_name, cert_key)
        
        # Return success - NO CORS headers (Function URL handles it)
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},  # Only Content-Type
            'body': json.dumps({
                'success': True,
                'message': 'Pledge submitted successfully',
                'employee_name': employee_name,
                'employee_id': employee_id,
                'department': department,
                'designation': designation,
                'pledge_id': pledge_id,
                'pdf_base64': pdf_base64,
                'certificate_size_kb': round(len(pdf_bytes) / 1024, 2)
            })
        }
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'message': f'Internal server error: {str(e)}'})
        }