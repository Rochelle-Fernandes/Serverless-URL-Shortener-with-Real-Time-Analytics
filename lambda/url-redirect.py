import json
import boto3
import os
import time

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'url-mappings')
ANALYTICS_TABLE = os.environ.get('ANALYTICS_TABLE', 'url-analytics')

def lambda_handler(event, context):
    try:
        short_code = event.get('pathParameters', {}).get('shortCode', '')

        if not short_code:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Short code missing'})}

        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'shortCode': short_code})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h2>🔗 Link not found or expired</h2>'
            }

        item = response['Item']
        current_time = int(time.time())

        if int(item.get('expiresAt', 9999999999)) < current_time:
            return {
                'statusCode': 410,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h2>⏰ This link has expired</h2>'
            }

        # Update click count
        table.update_item(
            Key={'shortCode': short_code},
            UpdateExpression='SET clickCount = clickCount + :inc',
            ExpressionAttributeValues={':inc': 1}
        )

        # Log analytics
        analytics_table = dynamodb.Table(ANALYTICS_TABLE)
        headers_data = event.get('headers') or {}
        analytics_table.put_item(Item={
            'shortCode': short_code,
            'timestamp': str(int(time.time() * 1000)),
            'ipAddress': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown'),
            'userAgent': headers_data.get('User-Agent', 'unknown')
        })

        return {
            'statusCode': 301,
            'headers': {
                'Location': item['originalUrl'],
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }

    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}