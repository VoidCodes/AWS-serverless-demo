import json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
dynamodb_table = dynamodb.Table('DemoTable')

status_check_path = '/status'
user_path = '/user'
users_path = '/users'

def lambda_handler(event, context):
    print('Request event: ', event)
    response = None
   
    try:
        http_method = event.get('httpMethod')
        path = event.get('path')

        if http_method == 'GET' and path == status_check_path:
            response = build_response(200, 'Service is operational')
        elif http_method == 'GET' and path == user_path:
            user_id = event['queryStringParameters']['userid']
            response = get_user(user_id)
        elif http_method == 'GET' and path == users_path:
            response = get_users()
        elif http_method == 'POST' and path == user_path:
            response = save_user(json.loads(event['body']))
        elif http_method == 'PATCH' and path == user_path:
            body = json.loads(event['body'])
            response = modify_user(body['userid'], body['updateKey'], body['updateValue'])
        elif http_method == 'DELETE' and path == user_path:
            body = json.loads(event['body'])
            response = delete_user(body['userid'])
        else:
            response = build_response(404, '404 Not Found')

    except Exception as e:
        print('Error:', e)
        response = build_response(400, 'Error processing request')
   
    return response

def get_user(user_id):
    # check if user exists
    existing_user_response = dynamodb_table.get_item(Key={'userid': user_id})
    if 'Item' not in existing_user_response:
        return build_response(404, f'User with userid {user_id} not found')
    try:
        response = dynamodb_table.get_item(Key={'userid': user_id})
        return build_response(200, response.get('Item'))
    except ClientError as e:
        print('Error:', e)
        return build_response(400, e.response['Error']['Message'])

def get_users():
    try:
        scan_params = {
            'TableName': dynamodb_table.name
        }
        return build_response(200, scan_dynamo_records(scan_params, []))
    except ClientError as e:
        print('Error:', e)
        return build_response(400, e.response['Error']['Message'])

def scan_dynamo_records(scan_params, item_array):
    response = dynamodb_table.scan(**scan_params)
    item_array.extend(response.get('Items', []))
   
    if 'LastEvaluatedKey' in response:
        scan_params['ExclusiveStartKey'] = response['LastEvaluatedKey']
        return scan_dynamo_records(scan_params, item_array)
    else:
        return {'users': item_array}

def save_user(request_body):
    try:
        dynamodb_table.put_item(Item=request_body)
        body = {
            'new_user': request_body
        }
        return build_response(200, body)
    except ClientError as e:
        print('Error:', e)
        return build_response(400, e.response['Error']['Message'])

def modify_user(user_id, update_key, update_value):
    # Check if user exists
    existing_user_response = dynamodb_table.get_item(Key={'userid': user_id})

    if 'Item' not in existing_user_response:
        return build_response(404, f'User with userid {user_id} not found')
    
    # Check if update_key exists in the user item
    existing_user = existing_user_response['Item']
    if update_key not in existing_user:
        return build_response(400, f'Attribute {update_key} does not exist for user {user_id}')

    try:
        response = dynamodb_table.update_item(
            Key={'userid': user_id},
            UpdateExpression=f'SET {update_key} = :value',
            ExpressionAttributeValues={':value': update_value},
            ReturnValues='UPDATED_NEW'
        )
        body = {
            'Operation': 'UPDATE',
            'Message': 'SUCCESS',
            'UpdatedAttributes': response
        }
        return build_response(200, body)
    except ClientError as e:
        print('Error:', e)
        return build_response(400, e.response['Error']['Message'])

def delete_user(user_id):
    # Check if user exists
    existing_user_response = dynamodb_table.get_item(Key={'userid': user_id})
    if 'Item' not in existing_user_response:
        return build_response(404, f'User with userid {user_id} not found')
    try:
        response = dynamodb_table.delete_item(
            Key={'userid': user_id},
            ReturnValues='ALL_OLD'
        )
        body = {
            'user_deleted': response
        }
        return build_response(200, body)
    except ClientError as e:
        print('Error:', e)
        return build_response(400, e.response['Error']['Message'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Check if it's an int or a float
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        # Let the base class default method raise the TypeError
        return super(DecimalEncoder, self).default(obj)

def build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }