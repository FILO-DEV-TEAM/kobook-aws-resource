import json
import boto3
import time
import traceback
from datetime import datetime, timedelta, timezone
from presigned_url import generate_presigned_url

# La_make_character

# user로 부터 받은 body data + user 고유 id dynamodb에 저장.
# return presigned url (client에서 업로드)


# datetime_utc = datetime.utcnow()
# timezone_kst = timezone(timedelta(hours=9))
# 현재 한국 시간
# datetime_kst = datetime_utc.astimezone(timezone_kst)
# print("current time:",datetime_kst.timestamp())

# 상태코드


def lambda_handler(event, context):
    # test code 확인
    print(event)
    # version check
    function_arn = context.invoked_function_arn
    env = function_arn.split(":")[-1]
    print(env)

    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
    table = dynamodb.Table(f"Dy_character_event_{env}")

    dynamodb_client = boto3.client("dynamodb")

    datetime_utc = datetime.utcnow()
    timezone_kst = timezone(timedelta(hours=9))
    # 현재 한국 시간
    datetime_kst = datetime_utc.astimezone(timezone_kst)
    # print("current time:",datetime_kst.timestamp())

    statusCode = 200
    try:
        httpMethod = event["httpMethod"]
    except:
        print("firebase user!!")

    try:
        httpMethod = event["routeKey"].split()[0]
    except:
        print("cognito user!!")

    if httpMethod != "POST":
        statusCode = 405
        return {"statusCode": statusCode, "body": json.dumps("Method Not Allowed")}

    # 이전 상태 확인
    try:
        # post 요청 관련해서 firebase user 추가 작업 필요
        item = event["body"]
        item = json.loads(item)

        item["name"] = "default"

        # cognito
        try:
            item["user_id"] = event["requestContext"]["authorizer"]["claims"][
                "cognito:username"
            ]
        except:
            print("firebase user!!")

        # firebase
        try:
            item["user_id"] = event["requestContext"]["authorizer"]["jwt"]["claims"][
                "user_id"
            ]
        except:
            print("cognito user!!")

        # ver이 global인지 확인!
        try:
            
            if item["ver"]:
                item["ver"]=item["ver"]
                print("hi global!")
            else:
                item["ver"] = ""
        except:
            item["ver"] = ""
            print("hi korean!")

        # 향후 flow에서 활용

        query = f"select * from Dy_character_event_{env} where user_id='{item['user_id']}' and status='ongoing';"
        result = dynamodb_client.execute_statement(Statement=query)
        print(result["Items"])
        for record in result["Items"]:
            user_id = record["user_id"]["S"]
            time_stamp = record["time_stamp"]["S"]
            query = f"UPDATE Dy_character_event_{env} SET status = 'cancel' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
            result = dynamodb_client.execute_statement(Statement=query)

        # query=f"select * from user_test where user_id='{item['user_id']}';"
        # result=dynamodb_client.execute_statement(Statement=query)
        # print(result["Items"])
        # 확인을 위한 작업!
        # temp=table_test.put_item(
        # Item={"user_id": item['user_id'],"num":int(item['age'])}
        # )

    except:
        statusCode = 500
        return {"statusCode": statusCode, "body": json.dumps("Internal Server Error!")}

    # put dynamodb
    try:
        # name은 공란 (향후 채워넣어야 함)
        # item['datetime']=datetime_kst.strftime('%Y-%m-%d-%H-%M-%S')
        item["time_stamp"] = str(int(datetime_kst.timestamp()))
        # cut/ 에 바로 올라감
        # item['object_key']='raw/'+item['user_id']+'/'+item['datetime']
        item["status"] = "ongoing"
        item["fail"] = "no"

        # get cloth h1,w1
        query = f"select h1,w1 from cloth_asset where cloth_name='{item['cloth']}';"
        result = dynamodb_client.execute_statement(Statement=query)
        w1 = result["Items"][0]["w1"]["N"]
        h1 = result["Items"][0]["h1"]["N"]
        item["w1"] = w1
        item["h1"] = h1

        # style 매핑
        print(item["style"])

        try:
            if item["style"] == "2D":
                item["style"] = "Anime isekai"
            elif item["style"] == "Pixar":
                item["style"] = "Pixar2"
            elif item["style"] == "Studio Ghibli":
                item["style"] = "Studio Ghibli::2, Miyazaki"
            elif item["style"] == "Curt Swan":
                item["style"] = "Elsa Beskow"
            elif item["style"] == "Water Color":
                item["style"] = "watercolor art by Winslow Homer"
            elif item["style"] == "Pencil Sketch":
                item["style"] = "Pencil Drawing by Paul Cézanne"
            elif item["style"] == "Carl Larsson":
                item["style"] = "watercolor art by Winslow Homer"
            elif item["style"] == "Children's book Illustration":
                item["style"] = "Children's Illustrations"

            temp = table.put_item(Item=item)
        except:
            err_msg = traceback.format_exc()
            print("style", err_msg)

        print(item["style"])
        # insert into (덮어씌우는 문제를 방지하기 위함)
        # print(item)
        # query=f"insert into Dy_character_event value {item}"
        # result=dynamodb_client.execute_statement(Statement=query)

    except:
        print("put dynamodb fail")
        statusCode = 400
        return {"statusCode": statusCode, "body": json.dumps("Bad Request")}

    """
    # get presigned url    
    try:
        s3_client=boto3.client('s3')
        bucket="s3-kkobook-character"
        key=item['object_key']+'.png'
        client_action="put_object"
        url = generate_presigned_url(
            s3_client, client_action, {'Bucket': bucket, 'Key': key}, 3600)

        bodyData={"presigned_url":url}
        jsonData = json.dumps(bodyData, ensure_ascii=False).encode('utf8')
        
    except:
        statusCode=500
        return {
            'statusCode': statusCode,
            'body': json.dumps('Internal Server Error!')
        }
    """

    """
    # SQS에 직접 전송
    try:
        # 최종 처리는 sqs에 연결된 lambda가 진행
        sqs = boto3.resource('sqs', region_name='ap-northeast-2')
        queue = sqs.get_queue_by_name(QueueName=f"SQS_make_character_{env}")
        temp_json={}
        temp_json['user_id']=item['user_id']
        temp_json['time_stamp']=item['time_stamp']
        print("hi")
        message_body=json.dumps(temp_json)
        response = queue.send_message(
            MessageBody=message_body,
        )
    except ClientError as error:
        logger.exception("Send Upscale message failed: %s", message_body)
        raise error
    """

    # image processing lambda invoke!
    try:
        lambda_client = boto3.client("lambda")

        payload = {
            "user_id": item["user_id"],
            "time_stamp": item["time_stamp"],
            "ver": item["ver"],
        }
        response = lambda_client.invoke(
            FunctionName="La_image_processing:prod",
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
    except:
        print("lambda invoke fail!")

    print("Good!")
    return {"statusCode": statusCode, "body": "Good"}
