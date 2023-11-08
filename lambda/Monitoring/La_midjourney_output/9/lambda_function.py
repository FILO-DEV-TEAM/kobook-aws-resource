import json
import boto3
import time
import requests
import os
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from JsonMorph import JsonMorph
from presigned_url import generate_presigned_url


# upscale 된 후의 image와 되지 않은 상태의 image를 따로 구분할 필요가 있을


def lambda_handler(event, context):
    # test code 확인
    print(event)
    # version check
    function_arn = context.invoked_function_arn
    env = function_arn.split(":")[-1]

    datetime_utc = datetime.utcnow()
    timezone_kst = timezone(timedelta(hours=9))
    # 현재 한국 시간
    datetime_kst = datetime_utc.astimezone(timezone_kst)

    # dynamodb
    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
    table_before = dynamodb.Table(f"Dy_midjourney_output_character_{env}")
    table_after = dynamodb.Table(f"Dy_midjourney_output_character_upscale_{env}")

    table_before_story = dynamodb.Table(f"Dy_midjourney_output_story_{env}")
    table_after_story = dynamodb.Table(f"Dy_midjourney_output_story_upscale_{env}")

    dynamodb_client = boto3.client("dynamodb")

    # TODO implement
    # print(event)
    # event parsing (from sqs) s3->sqs flow와 event flow 구성이 다름!
    try:
        # message_body: object_key, message_id, job_hash, img_url, state
        message_body = json.loads(event["Records"][0]["body"])
        temp = str(datetime_kst.timestamp())
        temp = temp.split(".")
        temp = temp[0] + temp[1][:3]
        time_sort_key = temp
        # print(message_body)
        # dynamodb에 query 가능

        pk = message_body["object_key"]
        # character
        if "s_t" not in message_body["object_key"]:
            user_id = message_body["object_key"].split("/")[1]
            time_stamp = message_body["object_key"].split("/")[2].split(".")[0]
        else:
            # story!!!
            user_id = message_body["object_key"].split("/")[1]
            time_stamp = message_body["object_key"].split("/")[2]
            in_dex = message_body["object_key"].split("/")[3]
            mode = message_body["object_key"].split("/")[4]

    except:
        print("event_parsing_fail!!!!!")
        print("hello ec2")
        # from ec2
        try:
            temp = str(datetime_kst.timestamp())
            temp = temp.split(".")
            temp = temp[0] + temp[1][:3]
            time_sort_key = temp

            # message_body: object_key, message_id, job_hash, img_url, state
            message_body = event

            pk = message_body["object_key"]
            # character
            if "s_t" not in message_body["object_key"]:
                user_id = message_body["object_key"].split("/")[1]
                time_stamp = message_body["object_key"].split("/")[2].split(".")[0]
            else:
                # story!!!
                user_id = message_body["object_key"].split("/")[1]
                time_stamp = message_body["object_key"].split("/")[2]
                in_dex = message_body["object_key"].split("/")[3]
                mode = message_body["object_key"].split("/")[4]
                # print(mode)
        except:
            print("event_parsing_fail!!!!!")
            print("hello sqs")

    # put dynamodb
    try:
        # character!!!
        if "s_t" not in message_body["object_key"]:
            message_body["user_id"] = user_id
            message_body["time_stamp"] = time_stamp

            if message_body["state"] == "before":
                message_body["time"] = time_sort_key

                # upscale이 필요한 img_url
                img_url = message_body["img_url"]
                job_hash = message_body["job_hash"]
                message_id = message_body["message_id"]

                # Dy_midjourney_check_prod 상태 업데이트!!
                try:
                    dynamodb_client = boto3.client(
                        "dynamodb", region_name="ap-northeast-2"
                    )
                    query = f"UPDATE Dy_midjourney_check_prod SET \"check\" = 'end' WHERE pk='{pk}';"
                    result = dynamodb_client.execute_statement(Statement=query)
                except:
                    print("dynamodb update fail!")

                # image segementation processing
                try:
                    response = requests.get(img_url)
                    img = Image.open(BytesIO(response.content))

                    width, height = img.size
                    left = 0
                    top = 0
                    right = width // 2
                    bottom = height // 2

                    # 이미지 4분할
                    img1 = img.crop((left, top, right, bottom))
                    img2 = img.crop((right, top, width, bottom))
                    img3 = img.crop((left, bottom, right, height))
                    img4 = img.crop((right, bottom, width, height))

                    print(img1.size)
                    # 분할된 이미지 저장
                    img1.save("/tmp/image1.jpg", quality=90)
                    img2.save("/tmp/image2.jpg", quality=90)
                    img3.save("/tmp/image3.jpg", quality=90)
                    img4.save("/tmp/image4.jpg", quality=90)

                    # s3 upload
                    s3 = boto3.client("s3")
                    s3.upload_file(
                        "/tmp/image1.jpg",
                        "s3-kkobook-character",
                        f"upscale/{user_id}/{time_stamp}/1.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image2.jpg",
                        "s3-kkobook-character",
                        f"upscale/{user_id}/{time_stamp}/2.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image3.jpg",
                        "s3-kkobook-character",
                        f"upscale/{user_id}/{time_stamp}/3.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image4.jpg",
                        "s3-kkobook-character",
                        f"upscale/{user_id}/{time_stamp}/4.jpg",
                    )
                except:
                    print("why?")

                # first image get api에서 활용 < Dy_midjourney_output_character_prod
                print(message_body)
                temp = table_before.put_item(Item=message_body)

                # ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # 캐릭터 또한 지연이 될 수 있음.
                # 현재 디스코드 채널 상의 job 개수를 고려해 sqs에 전달 (1개)
                try:
                    query = f"SELECT * from Dy_midjourney_check_{env} where \"check\"='start'"
                    result = dynamodb_client.execute_statement(Statement=query)
                    print(result)

                    # 시간순으로 오래된 사람부터 처리
                    time_sort = []
                    for item in result["Items"]:
                        pk = item["pk"]["S"]
                        time_stamp = pk.split("/")[2].split(".")[0]
                        time_sort.append([time_stamp, pk])

                    time_sort.sort()
                    print(time_sort)
                except:
                    print("query fail!")

                # lambda에 전달하기 전 현재 discord 상태 파악
                try:
                    query = f"SELECT * from Dy_midjourney_check_{env} where \"check\"='yes' or \"check\"='no'"
                    result = dynamodb_client.execute_statement(Statement=query)
                    # print(result)

                    # 현재 디스코드 채널 상에서 작업중인 job의 개수
                    job_number = len(result["Items"])
                    # print(job_number)
                except:
                    print("dynamodb query fail!!")

                try:
                    # job 2개는 남겨놓을 예정..
                    if (10 - job_number) > 0 and time_sort:
                        try:
                            # key에 pk 넣기
                            key = time_sort[0][1]
                            print(key)

                            # sqs의 시간지연으로 인해 발생할 수 있는 문제를 방지하기 위해 dynamodb update
                            try:
                                # dynamodb
                                dynamodb = boto3.resource(
                                    "dynamodb", region_name="ap-northeast-2"
                                )
                                table = dynamodb.Table(f"Dy_midjourney_check_{env}")
                                message_body_dy = {}
                                message_body_dy["pk"] = key
                                message_body_dy["check"] = "no"
                                # dynamodb put!
                                temp = table.put_item(Item=message_body_dy)
                            except:
                                print("dynamodb put fail!!")

                            # midjourney post lambda invoke!
                            try:
                                print("check!")
                                lambda_client = boto3.client("lambda")
                                payload = {"key": time_sort[0][1]}
                                response = lambda_client.invoke(
                                    FunctionName="La_post_midjourney_character:prod",
                                    InvocationType="Event",
                                    Payload=json.dumps(payload),
                                )
                            except:
                                print("lambda invoke fail!")

                        except:
                            print("something went wrong!!!!")
                            # slack noti 추가!
                except:
                    print("something went wrong!!")

                # s3에서 cut/user_id/time_stamp.png object 삭제.
                # cut image
                try:
                    # s3 delete
                    s3 = boto3.resource("s3")
                    # s3-kkobook-character
                    bucket = s3.Bucket("s3-kkobook-character")
                    prefix = f"cut/{user_id}.png"
                    for obj in bucket.objects.filter(Prefix=prefix):
                        print(obj.key)
                        s3.Object(bucket.name, obj.key).delete()
                except:
                    print("s3 delete fail!")

            # 향후 index별로 관리할 수 있도록 time col을 정렬키로 사용함
            elif message_body["state"] == "after":
                print("after:", message_body)
                message_body["time"] = time_sort_key
                temp = table_after.put_item(Item=message_body)
        else:
            # 유저가 동화 생성 과정 중 회원탈퇴를 진행하는 경우 로직이 꼬이는 문제가 발생할 수 있으므로 DB에 해당 user_id가 존재하는지 확인 후 진행
            # story!!!
            message_body["user_id"] = user_id
            message_body["time_stamp"] = time_stamp
            message_body["in_dex"] = in_dex

            # db check 작업 > 해당 유저가 story_event에 존재하지 않으면 삭제된 것!
            dynamodb_client = boto3.client("dynamodb")
            # ongoing 상태까지 확인함으로 내부적으로 로직 테스트를 하더라도 문제가 발생하지 않음! (이전의 데이터를 가지고 하기에)
            query = f"select * from Dy_story_event_{env} where user_id='{user_id}' and status='ongoing';"
            result = dynamodb_client.execute_statement(Statement=query)
            # print(result)
            if len(result["Items"]) == 0:
                print("회원 탈퇴한 유저!!")
                return {"statusCode": 200, "body": json.dumps("bye!")}

            if message_body["state"] == "before":
                message_body["time"] = time_sort_key

                # print(message_body)
                temp = table_before_story.put_item(Item=message_body)

                img_url = message_body["img_url"]

                # Dy_midjourney_check_prod 상태 업데이트!!
                try:
                    dynamodb_client = boto3.client(
                        "dynamodb", region_name="ap-northeast-2"
                    )
                    query = f"UPDATE Dy_midjourney_check_story_prod SET \"check\" = 'end' WHERE pk='{pk}' and mode='{mode}';"
                    result = dynamodb_client.execute_statement(Statement=query)
                except:
                    print("dynamodb update fail!")
                print("hello")

                # image segementation processing
                try:
                    response = requests.get(img_url)
                    img = Image.open(BytesIO(response.content))

                    width, height = img.size
                    left = 0
                    top = 0
                    right = width // 2
                    bottom = height // 2

                    # 이미지 4분할
                    img1 = img.crop((left, top, right, bottom))
                    img2 = img.crop((right, top, width, bottom))
                    img3 = img.crop((left, bottom, right, height))
                    img4 = img.crop((right, bottom, width, height))

                    # print(img1.size)
                    # 분할된 이미지 저장
                    img1.save("/tmp/image1.jpg", quality=90)
                    img2.save("/tmp/image2.jpg", quality=90)
                    img3.save("/tmp/image3.jpg", quality=90)
                    img4.save("/tmp/image4.jpg", quality=90)

                    # s3 upload
                    s3 = boto3.client("s3")
                    s3.upload_file(
                        "/tmp/image1.jpg",
                        "s3-kkobook-story-image",
                        f"upscale/{user_id}/{time_stamp}/{in_dex}/1.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image2.jpg",
                        "s3-kkobook-story-image",
                        f"upscale/{user_id}/{time_stamp}/{in_dex}/2.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image3.jpg",
                        "s3-kkobook-story-image",
                        f"upscale/{user_id}/{time_stamp}/{in_dex}/3.jpg",
                    )
                    s3.upload_file(
                        "/tmp/image4.jpg",
                        "s3-kkobook-story-image",
                        f"upscale/{user_id}/{time_stamp}/{in_dex}/4.jpg",
                    )

                except:
                    print("why?")

                # 만약 동화의 페이지가 모두 생성되었다면 다음 작업 진행
                try:
                    env = "prod"
                    dynamodb_client = boto3.client(
                        "dynamodb", region_name="ap-northeast-2"
                    )
                    query = f"select in_dex from Dy_midjourney_output_story_{env} where user_id='{user_id}' and time_stamp='{time_stamp}';"
                    result = dynamodb_client.execute_statement(Statement=query)

                    # 모든 책의 작업이 완료된 상황!
                    if len(result["Items"]) == 8:
                        print("Hi~")

                        # 해당 작업은 향후 조
                        """
                        # dynamodb processing (정리)
                        #query=f"UPDATE Dy_story_event_{env} SET status = 'finish' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
                        #result=dynamodb_client.execute_statement(Statement=query)
                        
                        
                        # title 가져오기
                        query=f"select title from Dy_story_event_{env} where user_id='{user_id}' and time_stamp='{time_stamp}'"
                        result=dynamodb_client.execute_statement(Statement=query)
                        
                        title=result["Items"][0]['title']['S']
                    
                        # Dy_user_book 업데이트!
                        dynamodb = boto3.resource('dynamodb',region_name='ap-northeast-2')
            
                        # dynamodb update
                        query=f"UPDATE Dy_user_book_{env} SET status = 'finish' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
                        result=dynamodb_client.execute_statement(Statement=query)
                        
                        query=f"UPDATE Dy_user_book_{env} SET title = '{title}' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
                        result=dynamodb_client.execute_statement(Statement=query)
                        """

                        try:
                            # presigned url 발급!! (초기는 모든 페이지의 index가 1로 고정됨)
                            dynamodb = boto3.resource(
                                "dynamodb", region_name="ap-northeast-2"
                            )
                            table = dynamodb.Table(f"Dy_story_image_prod")

                            temp_dict = {}
                            temp_dict["user_id"] = user_id
                            temp_dict["time_stamp"] = time_stamp

                            # 현재는 8페이지 고정
                            temp_dict["page_index"] = "11111111"

                            s3_client = boto3.client("s3")
                            client_action = "get_object"
                            bucket_pre = "s3-kkobook-story-image"

                            for page_num in range(1, 9):
                                time.sleep(0.5)
                                # 처음엔 1페이지 고정!
                                key = f"upscale/{user_id}/{time_stamp}/{page_num}/1.jpg"
                                url = generate_presigned_url(
                                    s3_client,
                                    client_action,
                                    {"Bucket": bucket_pre, "Key": key},
                                    604800,
                                )
                                temp_dict[str(page_num)] = url

                            temp = table.put_item(Item=temp_dict)
                        except:
                            print("why??!")

                        # 프론트와 협의 필요
                        """
                        # firebase noti!
                        try:
                            # firebase에 noti 보내기
                            reqUrl = "firebase url"
                            
                            headersList = {
                             "Content-Type": "application/json" 
                            }
                            
                            payload = json.dumps({
                              "user_id": f"{user_id}"
                            })
                            
                            response = requests.request("POST", reqUrl, data=payload,  headers=headersList)
                        except:
                            print("firebase noti fail!!")
                        """

                except:
                    print("new feature error!")

                # 현재 디스코드 채널 상의 job 개수를 고려해 lambda에 전달 mode:0 에 대한 처리..
                try:
                    query = f"SELECT * from Dy_midjourney_check_story_{env} where \"check\"='yes' or \"check\"='no' and mode='{mode}'"
                    result = dynamodb_client.execute_statement(Statement=query)
                    # print(result)

                    # 현재 디스코드 채널 상에서 작업중인 job의 개수
                    job_number = len(result["Items"])
                    print(f"job_number:{job_number}, mode: {mode}")
                except:
                    print("dynamodb query fail!!")

                try:
                    query = f"SELECT * from Dy_midjourney_check_story_{env} where \"check\"='start' and mode='{mode}'"
                    result = dynamodb_client.execute_statement(Statement=query)
                    # print(result)
                    # 시간순으로 오래된 요청부터 처리 및 낮은 in_dex부터 생성
                    time_sort = []
                    for item in result["Items"]:
                        pk = item["pk"]["S"]
                        in_dex = pk.split("/")[-1]
                        time_stamp = pk.split("/")[2]
                        time_sort.append([time_stamp, in_dex, pk])
                    time_sort.sort()
                    print(f"time_sort: {time_sort}")

                    if (11 - job_number) > 0 and time_sort:
                        # 시간지연으로 인한 꼬임 방지
                        try:
                            # update
                            dynamodb_client = boto3.client("dynamodb")
                            query = f"UPDATE Dy_midjourney_check_story_{env} SET \"check\" = 'no' WHERE pk='{time_sort[0][2]}' and mode='{mode}';"
                            result = dynamodb_client.execute_statement(Statement=query)
                        except:
                            print("dynamodb update fail!!")

                        # midjourney post lambda invoke!
                        try:
                            lambda_client = boto3.client("lambda")
                            payload = {"pk": time_sort[0][2], "mode": mode}
                            response = lambda_client.invoke(
                                FunctionName="La_post_midjourney_story:prod",
                                InvocationType="Event",
                                Payload=json.dumps(payload),
                            )
                        except:
                            print("lambda invoke fail!")
                except:
                    print("something went wrong!!")

                # post upscale request
                """
                try:
                    load_dotenv("key.env")
                    MID_JOURNEY_ID = os.getenv("MID_JOURNEY_ID")
                    SERVER_ID = os.getenv("SERVER_ID")
                    CHANNEL_ID = os.getenv("CHANNEL_ID")
                    header = {'authorization' : os.getenv("VIP_TOKEN")}
                    URL = "https://discord.com/api/v9/interactions"
                    StorageURL = "https://discord.com/api/v9/channels/" + CHANNEL_ID + "/attachments"
                    
                    # 일단 index 1번 고정!!
                    for index in range(1,2):
                        __payload = JsonMorph(MID_JOURNEY_ID, SERVER_ID, CHANNEL_ID, index, message_id, job_hash, "upsample")
                        response =  requests.post(url = URL, json = __payload, headers = header)
                        time.sleep(1)
                except:
                    print("Not!!")
                    statusCode=500
                    return {
                        'statusCode': statusCode,
                        'body': json.dumps('!!!!!')
                    }
                """
            # 향후 index별로 관리할 수 있도록 time col을 정렬키로 사용함
            # 최신버전에선 사라질 코드
            elif message_body["state"] == "after":
                print("after:", message_body)
                message_body["time"] = time_sort_key

                # db check 작업 > 해당 유저가 story_event에 존재하지 않으면 삭제된 것!
                dynamodb_client = boto3.client("dynamodb")
                query = f"select * from Dy_story_event_{env} where user_id='{user_id}' and status='ongoing';"
                result = dynamodb_client.execute_statement(Statement=query)
                print(result)
                if len(result["Items"]) == 0:
                    print("회원 탈퇴한 유저!!")
                    return {"statusCode": 200, "body": json.dumps("bye!")}

                temp = table_after_story.put_item(Item=message_body)

                # 책이 모두 완성되었는지 확인!
                query = f"select in_dex from Dy_midjourney_output_story_upscale_{env} where user_id='{user_id}' and time_stamp='{time_stamp}';"
                result = dynamodb_client.execute_statement(Statement=query)

                # 책이 모두 완성됨!
                print(len(result["Items"]))
                if len(result["Items"]) == 8:
                    # sqs 전송 (SQS_make_book)
                    try:
                        # 최종 처리는 sqs에 연결된 lambda가 진행
                        sqs = boto3.resource("sqs", region_name="ap-northeast-2")
                        queue = sqs.get_queue_by_name(QueueName=f"SQS_make_book_{env}")
                        temp_json = {}
                        temp_json["user_id"] = user_id
                        temp_json["time_stamp"] = time_stamp
                        message_body = json.dumps(temp_json)
                        response = queue.send_message(
                            MessageBody=message_body,
                        )
                    except ClientError as error:
                        logger.exception(
                            "Send Upscale message failed: %s", message_body
                        )
                        raise error

    except:
        print("put_dynamodb fail!!!!!")

    print("Good!")
    return {"statusCode": 200, "body": json.dumps("Hello from Lambda!")}
