import json
import boto3
import random
import string
import time
import os
import urllib.request
import base64

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'url-mappings')
S3_BUCKET = os.environ.get('S3_BUCKET', 'url-shortener-dashboard-ras')
BASE_URL = os.environ.get('BASE_URL', 'https://example.com')

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_qr_code(short_url, short_code):
    try:
        import qrcode
        import io
        qr = qrcode.make(short_url)
        buffer = io.BytesIO()
        qr.save(buffer, format='PNG')
        buffer.seek(0)
        s3_key = f"qr/{short_code}.png"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=buffer.getvalue(),
            ContentType='image/png'
        )
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
    except Exception as e:
        print(f"QR generation error: {e}")
        return None

def lambda_handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    try:
        body = json.loads(event.get('body', '{}'))
        original_url = body.get('url', '').strip()
        expiry_days = int(body.get('expiryDays', 30))
        custom_code = body.get('customCode', '').strip()

        if not original_url:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'URL is required'})
            }

        if not original_url.startswith(('http://', 'https://')):
            original_url = 'https://' + original_url

        short_code = custom_code if custom_code else generate_short_code()
        table = dynamodb.Table(TABLE_NAME)

        # Check if custom code already exists
        if custom_code:
            existing = table.get_item(Key={'shortCode': short_code})
            if 'Item' in existing:
                return {
                    'statusCode': 409,
                    'headers': headers,
                    'body': json.dumps({'error': 'Custom code already taken'})
                }

        short_url = f"{BASE_URL}/r/{short_code}"
        expires_at = int(time.time()) + (expiry_days * 86400)
        qr_url = generate_qr_code(short_url, short_code)

        table.put_item(Item={
            'shortCode': short_code,
            'originalUrl': original_url,
            'createdAt': str(int(time.time())),
            'expiresAt': expires_at,
            'clickCount': 0,
            'qrCodeUrl': qr_url or ''
        })

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'shortCode': short_code,
                'shortUrl': short_url,
                'originalUrl': original_url,
                'qrCodeUrl': qr_url,
                'expiresAt': expires_at
            })
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }