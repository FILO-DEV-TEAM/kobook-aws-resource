import json
import boto3
import time
import os
import requests
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from JsonImagine import JsonImagine

# style prompt 필요!!!

# dynamodb
dynamodb_client = boto3.client("dynamodb")


def lambda_handler(event, context):
    # test code 확인
    print(event)
    # version check
    function_arn = context.invoked_function_arn
    env = function_arn.split(":")[-1]

    # event parsing (from sqs)
    # print(event)
    try:
        # print(event)
        message_body = json.loads(event["Records"][0]["body"])
        # bucket_name=message_body['Records'][0]['s3']['bucket']['name']
        # object_key=message_body['Records'][0]['s3']['object']['key']
        object_key = message_body["key"]
        # object_key만 있으면 됨
        print(object_key)
        user_id = object_key.split("/")[1]
        time_stamp = object_key.split("/")[2].split(".")[0]
        # print("check!!")
        query = f"SELECT gender,style,age FROM Dy_character_event_{env} where user_id='{user_id}' and time_stamp='{time_stamp}'"
        result = dynamodb_client.execute_statement(Statement=query)
        # print(result)
        # print("check!!")

        # 다시 N으로 바꿔줘야함
        age = str(result["Items"][0]["age"]["N"])
        gender = result["Items"][0]["gender"]["S"]
        style = result["Items"][0]["style"]["S"]
    except:
        print("event_parsing_fail!!!!!")

    # lambda invoke test
    try:
        object_key = event["key"]
        user_id = object_key.split("/")[1]
        time_stamp = object_key.split("/")[2].split(".")[0]
        # print("check!!")
        query = f"SELECT gender,style,age FROM Dy_character_event_{env} where user_id='{user_id}' and time_stamp='{time_stamp}'"
        result = dynamodb_client.execute_statement(Statement=query)
        # print(result)
        # print("check!!")

        # 다시 N으로 바꿔줘야함
        age = str(result["Items"][0]["age"]["N"])
        gender = result["Items"][0]["gender"]["S"]
        style = result["Items"][0]["style"]["S"]

    except:
        print("hello sqs")

    print(style)
    # post midjourney!!!
    try:
        load_dotenv("key.env")
        MID_JOURNEY_ID = os.getenv("MID_JOURNEY_ID")
        SERVER_ID = os.getenv("SERVER_ID")
        CHANNEL_ID = os.getenv("CHANNEL_ID")
        header = {"authorization": os.getenv("VIP_TOKEN")}
        URL = "https://discord.com/api/v9/interactions"
        StorageURL = (
            "https://discord.com/api/v9/channels/" + CHANNEL_ID + "/attachments"
        )

        my_redirect_url = "my_redirect_url"
        # {my_redirect_url}/{object_key}
        if style == "Anime isekai":
            prompt = f"<#{object_key}> {my_redirect_url}/{object_key}, in age of {age} years, {gender}, asian, cute, portrait,smiling, full body, main character, emotional, surreal, vibrant, Anime isekai --turbo"
        elif style == "Pixar::2":
            prompt = f"<#{object_key}> {my_redirect_url}/{object_key}, in age of {age} years, {gender}, asian, cute, portrait,smiling, full body, main character, emotional, surreal, vibrant, no background, Pixar::2, --turbo --iw 1"
        elif style == "Studio Ghibli::2, Miyazaki":
            prompt = f"<#{object_key}> {my_redirect_url}/{object_key}, in age of {age} years, {gender}, cute, portrait,smiling, full body, main character, emotional, surreal, Studio Ghibli::2, Miyazaki --iw 0.6 --turbo"
        elif style == "Curt Swan":
            prompt = f"<#{object_key}> {my_redirect_url}/{object_key}, in age of {age} years, {gender}, asian, portrait, smiling,cute, full body, by Elsa Beskow --turbo"
        else:
            prompt = f"<#{object_key}> {my_redirect_url}/{object_key}, in age of {age} years, {gender}, asian, portrait, smiling,cute, full body, by {style} --turbo "

        __payload = JsonImagine(MID_JOURNEY_ID, SERVER_ID, CHANNEL_ID, prompt)

        print(f"prompt: {prompt}")
        # print(__payload)

        try:
            # Dy_midjourney_check_prod 기록
            datetime_utc = datetime.utcnow()
            timezone_kst = timezone(timedelta(hours=9))
            # 현재 한국 시간
            datetime_kst = datetime_utc.astimezone(timezone_kst)
            temp = str(datetime_kst.timestamp())
            temp = temp.split(".")
            temp = temp[0] + temp[1][:3]
            time_sort_key = temp

            # dynamodb
            dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
            table = dynamodb.Table(f"Dy_midjourney_check_{env}")
            message_body = {}
            message_body["pk"] = object_key
            message_body["time"] = time_sort_key
            message_body["prompt"] = prompt
            message_body["check"] = "no"
            try:
                # dynamodb put!
                temp = table.put_item(Item=message_body)
            except:
                print("dynamodb put fail!!")

        except:
            print("put_dynamodb fail!!")

        # post to midjourney!!!
        while True:
            response = requests.post(url=URL, json=__payload, headers=header)
            if response.status_code != 204:
                time.sleep(1)
            else:
                break
    except:
        print("OTL...")

    # appeal monitoring lambda invoke!
    try:
        lambda_client = boto3.client("lambda")

        payload = {"pk": object_key, "time": time_sort_key, "prompt": prompt}
        response = lambda_client.invoke(
            FunctionName="La_midjourney_check:prod",
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
    except:
        print("lambda invoke fail!")

    print("Good!")
    return {"statusCode": 202, "body": json.dumps("Success")}
