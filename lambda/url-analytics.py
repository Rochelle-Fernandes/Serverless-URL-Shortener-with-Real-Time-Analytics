import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'url-mappings')
ANALYTICS_TABLE = os.environ.get('ANALYTICS_TABLE', 'url-analytics')

def lambda_handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, OPTIONS'
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    try:
        short_code = (event.get('pathParameters') or {}).get('shortCode', '')

        if not short_code:
            table = dynamodb.Table(TABLE_NAME)
            response = table.scan()
            items = response.get('Items', [])
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'urls': items}, default=str)
            }

        table = dynamodb.Table(TABLE_NAME)
        url_data = table.get_item(Key={'shortCode': short_code})

        if 'Item' not in url_data:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Short code not found'})
            }

        analytics_table = dynamodb.Table(ANALYTICS_TABLE)
        clicks = analytics_table.query(
            KeyConditionExpression=Key('shortCode').eq(short_code)
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'url': url_data['Item'],
                'clicks': clicks.get('Items', [])
            }, default=str)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }