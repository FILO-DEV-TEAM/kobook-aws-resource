import json
import boto3
import time
import os
import requests
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from JsonImagine import JsonImagine

# to filo.team.dev2@gmail.com discord channel

# dynamodb
dynamodb_client=boto3.client('dynamodb')
def lambda_handler(event, context):
    
    # 주기적으로 ping 요청을 보낼 것임.
    print(event)
    # version check
    function_arn = context.invoked_function_arn
    env=function_arn.split(":")[-1]
    print(env)
    
    # post midjourney!!!
    try:
        load_dotenv("key.env")
        
        # FILO2 계정
        MID_JOURNEY_ID_1 = os.getenv("MID_JOURNEY_ID_1")
        SERVER_ID_1 = os.getenv("SERVER_ID_1")
        CHANNEL_ID_1= os.getenv("CHANNEL_ID_1")
        header_1 = {'authorization' : os.getenv("VIP_TOKEN_1")}
        
        # FILO 계정
        MID_JOURNEY_ID_2 = os.getenv("MID_JOURNEY_ID_2")
        SERVER_ID_2 = os.getenv("SERVER_ID_2")
        CHANNEL_ID_2= os.getenv("CHANNEL_ID_2")
        header_2 = {'authorization' : os.getenv("VIP_TOKEN_2")}
        
        URL = "https://discord.com/api/v9/interactions"
        StorageURL_1 = "https://discord.com/api/v9/channels/" + CHANNEL_ID_1 + "/attachments"
        StorageURL_2 = "https://discord.com/api/v9/channels/" + CHANNEL_ID_2 + "/attachments"
        
  
        
        # 현재 FILO채널, FILO2 채널의 상태 트래킹
        
        # 현재 디스코드 채널 상의 job 개수를 고려해 lambda에 전달
        dynamodb_client=boto3.client('dynamodb')
        try:
            # 1번채널
            query=f"SELECT * from Dy_midjourney_check_{env} where mode='1' and (\"check\"='yes' or \"check\"='no')";
            print(query)
            result=dynamodb_client.execute_statement(Statement=query)
            print(result)
            
            # 현재 디스코드 채널 상에서 작업중인 job의 개수
            job_number_1=len(result["Items"])
            print(f"job_number_1:{job_number_1}")
        except:
            print("dynamodb query fail!!")

        # 현재 디스코드 채널 상의 job 개수를 고려해 lambda에 전달
        dynamodb_client=boto3.client('dynamodb')
        try:
            # 2번채널
            query=f"SELECT * from Dy_midjourney_check_{env} where mode='2' and (\"check\"='yes' or \"check\"='no')";
            result2=dynamodb_client.execute_statement(Statement=query)
            #print(result)
            
            # 현재 디스코드 채널 상에서 작업중인 job의 개수
            job_number_2=len(result2["Items"])
            print(f"job_number_2:{job_number_2}")
        except:
            print("dynamodb query fail!!")
            
        # mode는 보내기 직전에 붙임
        dynamodb_client=boto3.client('dynamodb')
        try:
            query=f"SELECT * from Dy_midjourney_check_{env} where \"check\"='start'"
            result=dynamodb_client.execute_statement(Statement=query)
            #print(result)
            # 시간순으로 오래된 요청부터 처리 및 낮은 in_dex부터 생성
            time_sort=[]
            for item in result["Items"]:
                pk=item['pk']['S']
                time_stamp=pk.split('/')[1]
                time_sort.append([time_stamp,pk])
            time_sort.sort()        
            print(time_sort)
        except:
            print("check fail!")
            
# ------------------------------------------------------mode1--------------------------------------------------------------

        if (3-job_number_1)>0 and time_sort:
            # 시간지연으로 인한 꼬임 방지
            try:
                # update
                dynamodb_client=boto3.client('dynamodb')
                query=f"UPDATE Dy_midjourney_check_{env} SET mode = '1' WHERE pk='{time_sort[0][1]}';"
                result=dynamodb_client.execute_statement(Statement=query)
                
                time.sleep(1)
                query=f"UPDATE Dy_midjourney_check_{env} SET \"check\" = 'no' WHERE pk='{time_sort[0][1]}' and mode='1';"
                result=dynamodb_client.execute_statement(Statement=query)
            except:
                print("dynamodb update fail!!")
            
            # query와 관련한 이슈가 발생하는 경우가 존재함.
            ct=0
            while ct<5:
                try:
                    dynamodb_client=boto3.client('dynamodb')
                    query=f"SELECT prompt FROM Dy_midjourney_check_{env} where pk='{time_sort[0][1]}' and mode='1'"
                    result=dynamodb_client.execute_statement(Statement=query)
                    prompt=result["Items"][0]['prompt']['S']
                    break
                except:
                    print("why?")
                    time.sleep(1)
                    ct+=1
            
            # midjourney bot 
            __payload=JsonImagine(MID_JOURNEY_ID_1, SERVER_ID_1, CHANNEL_ID_1, prompt)
            
            print(__payload['session_id'])
            
            # post to midjourney!!!
            while True:
                response = requests.post(url = URL, json = __payload, headers = header_1)
                if response.status_code!=204:
                    time.sleep(1)
                else:
                    break
                
            # appeal monitoring lambda invoke!
            try:
                lambda_client=boto3.client('lambda')
                
                payload={
                    'pk':time_sort[0][1],
                    'prompt':prompt,
                    'mode':'1'
                }
                response = lambda_client.invoke(
                    FunctionName='La_midjourney_check_story:dev',
                    InvocationType='Event',
                    Payload=json.dumps(payload)
                )
            except:
                print("lambda invoke fail!")
            
        
            print("Good! mode 1")
            return {
                'statusCode': 200,
                'body': json.dumps('Hello')
            }

    
# ------------------------------------------------------mode2--------------------------------------------------------------
        
        if (3-job_number_2)>0 and time_sort:
            # 시간지연으로 인한 꼬임 방지
            try:
                # update
                dynamodb_client=boto3.client('dynamodb')
                query=f"UPDATE Dy_midjourney_check_{env} SET mode = '2' WHERE pk='{time_sort[0][1]}';"
                result=dynamodb_client.execute_statement(Statement=query)
                
                time.sleep(1)
                query=f"UPDATE Dy_midjourney_check_{env} SET \"check\" = 'no' WHERE pk='{time_sort[0][1]}' and mode='2';"
                result=dynamodb_client.execute_statement(Statement=query)
            except:
                print("dynamodb update fail!!")
        
            # query와 관련한 이슈가 발생하는 경우가 존재함.
            ct=0
            while ct<5:
                try:
                    dynamodb_client=boto3.client('dynamodb')
                    query=f"SELECT prompt FROM Dy_midjourney_check_{env} where pk='{time_sort[0][1]}' and mode='2'"
                    result=dynamodb_client.execute_statement(Statement=query)
                    prompt=result["Items"][0]['prompt']['S']
                    break
                except:
                    print("why?")
                    time.sleep(1)
                    ct+=1
            
            # midjourney bot 
            __payload=JsonImagine(MID_JOURNEY_ID_2, SERVER_ID_2, CHANNEL_ID_2, prompt)
            
            print(__payload['session_id'])
            
            # post to midjourney!!!
            while True:
                response = requests.post(url = URL, json = __payload, headers = header_2)
                if response.status_code!=204:
                    time.sleep(1)
                else:
                    break
                
            # appeal monitoring lambda invoke!
            try:
                lambda_client=boto3.client('lambda')
                
                payload={
                    'pk':time_sort[0][1],
                    'prompt':prompt,
                    'mode':'2'
                }
                response = lambda_client.invoke(
                    FunctionName='La_midjourney_check_story:dev',
                    InvocationType='Event',
                    Payload=json.dumps(payload)
                )
            except:
                print("lambda invoke fail!")
            
        
            print("Good! mode 2")
            return {
                'statusCode': 200,
                'body': json.dumps('Hello')
            }

    except:
        print("OTL...")
        
    print("full!!!")
    return {
        'statusCode': 200,
        'body': json.dumps('Hello La_post_midjourney_story')
    }
