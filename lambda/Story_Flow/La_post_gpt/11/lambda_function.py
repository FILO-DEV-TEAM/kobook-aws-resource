import json
import os
import openai
import boto3
import traceback
import random
import time
import urllib.request
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from post_slack import post_slack

load_dotenv("key.env")

# Load your API key from an environment variable or secret management service
openai.api_key = os.getenv("OPEN_API_KEY")


def make_stroy(
    messages, temperature=1, top_p=1, n=1, presence_penalty=0, frequency_penalty=0
):
    chat_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        n=n,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    output = chat_response["choices"][0]["message"]["content"]
    return output


def make_stroy_gpt_4(
    messages, temperature=1, top_p=1, n=1, presence_penalty=0, frequency_penalty=0
):
    chat_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        n=n,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    output = chat_response["choices"][0]["message"]["content"]
    return output


def post_slack_book(argStr):
    message = argStr
    send_data = {
        "text": message,
    }
    send_text = json.dumps(send_data)
    request = urllib.request.Request(
        "slack webhook url",
        data=send_text.encode("utf-8"),
    )
    # slack webhook url

    with urllib.request.urlopen(request) as response:
        slack_message = response.read()


# sqs에서 전달받은 user_id, timestamp 토대로 글 생성에 필요한 데이터를 쿼리 해오기
def lambda_handler(event, context):
    # test code 확인
    print(event)
    # version check
    function_arn = context.invoked_function_arn
    env = function_arn.split(":")[-1]
    # just concurreny
    env = "prod"
    dynamodb_client = boto3.client("dynamodb")
    # event parsing
    try:
        # print(event)
        # print(event)
        message_body = json.loads(event["Records"][0]["body"])
        # bucket_name=message_body['Records'][0]['s3']['bucket']['name']
        # object_key=message_body['Records'][0]['s3']['object']['key']
        user_id = message_body["user_id"]
        time_stamp = message_body["time_stamp"]
        try:
            version = message_body["version"]
        except:
            version = "1"
        print(version)

        start_time = time.time()
        # slack 노티
        try:
            post_slack_book(f"book make request occur! {user_id}, {time_stamp}")
        except:
            print("noti error!")
        end_time = time.time()
        print(f"post_slack: {end_time - start_time:.5f}")

    except:
        print("why??")

    if version == "1":
        try:
            # print(user_id,time_stamp)
            query = f"SELECT gender,age,name,major,middle,sub FROM Dy_story_event_{env} where user_id='{user_id}' and time_stamp='{time_stamp}'"
            # print(query)
            result = dynamodb_client.execute_statement(Statement=query)
            # print(result)
            # print("check!!")

            # 다시 N으로 바꿔줘야함
            age = str(result["Items"][0]["age"]["S"])
            gender = result["Items"][0]["gender"]["S"]
            name = result["Items"][0]["name"]["S"]
            major = result["Items"][0]["major"]["S"]
            middle = result["Items"][0]["middle"]["S"]
            sub = result["Items"][0]["sub"]["S"]

        except:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: event_parsing_fail!"
            post_slack(notification)
            print("event_parsing_fail!!!!!")
            return {"statusCode": 200, "body": "..."}
        # 글 생성

        message = [
            {
                "role": "user",
                "content": "너는 아이들을 위한 동화 생성하고 이야기해 주는 작가 선생님으로, 아이들에게 이야기해주는 톤을 유지하며, 아래의 캐릭터설정을 기반으로 동화분류와 제약사항을 참고하여 그 구성과 아래 출력형식(JSON)에 맞춰 동화를 작성해라.\n동화분류:\n대분류: %(major)s; 중분류: %(middle)s; 소분류: %(sub)s \n제약사항:\n최대페이지수: 8;\n페이지수: 8;\n페이지의양: 최소 30 tokens;\n제목: 새로운 캐릭터 등장과 함께 소개할수 있는 제목 구성\n대상: 3~6세\n말투: 했어요\n 캐릭터설정: %(name)s, %(age)s살, %(gender)s \n 출력형식:{제목:동화의 제목, 1:페이지 내용, 2:페이지 내용, 3:페이지 내용, 4:페이지 내용, 5:페이지 내용, 6:페이지 내용, 7:페이지 내용, 8:페이지 내용}"
                % {
                    "major": major,
                    "middle": middle,
                    "sub": sub,
                    "name": name,
                    "age": age,
                    "gender": gender,
                },
            }
        ]

        # story=make_stroy(message,temperature=0.75)

        # print(message)

        # json 형식 검사
        temperature = 1
        flag = False
        while temperature > 0.7:
            try:
                story = make_stroy_gpt_4(message, temperature=temperature)
                print(story)
                story_json = json.loads(story)
                if len(list(story_json.keys())) == 9:
                    title = story_json[list(story_json.keys())[0]]
                    # print(title)
                    del story_json[list(story_json.keys())[0]]

                    f = True
                    # gpt에서 글이 생성되지 않는 경우 방지...
                    for key in list(story_json.keys()):
                        if len(story_json[key]) == 0:
                            f = False
                    if f:
                        flag = True
                        break
                else:
                    temperature -= 0.1
            except:
                try:
                    check = story.split("{")
                    if len(check[0]) > 1:
                        if len(check) == 2:
                            temp_story = "{" + check[1]
                            print(temp_story)
                            story_json = json.loads(temp_story)
                            try:
                                if len(list(story_json.keys())) == 9:
                                    title = story_json[list(story_json.keys())[0]]
                                    print(title)
                                    del story_json[list(story_json.keys())[0]]

                                    f = True
                                    # gpt에서 글이 생성되지 않는 경우 방지...
                                    for key in list(story_json.keys()):
                                        if len(story_json[key]) == 0:
                                            f = False
                                    if f:
                                        flag = True
                                        break
                            except:
                                pass
                except:
                    print("haha")

                temperature -= 0.1
                err_msg = traceback.format_exc()
                print("1", err_msg)

        if not flag:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: gpt_fail!!"
            post_slack(notification)
            print("gpt fail!!!")
            return {"statusCode": 200, "body": "gg"}
        try:
            story_image = {}

            story_josn_key = list(story_json.keys())

            for key_index in range(len(story_josn_key)):
                print(story_json[story_josn_key[key_index]])

                # 주인공 등장
                if key_index % 2 == 0:
                    message_image = [
                        {
                            "role": "user",
                            "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                        },
                        {
                            "role": "assistant",
                            "content": "(),(),()",
                        },
                        {
                            "role": "user",
                            "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{major}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                        },
                    ]

                    """
                    message_image = [
                        {
                            "role": "user",
                            "content": "너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래  제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n한 날, 나현이는 호기심이 많은 소년이었습니다. 학교 과학 수업에서 배운 보물 찾기에 흥미를 느껴 함께 보물을 찾아보자고 친구들에게 제안했어요.\n캐릭터: \n이름:나현, \n나이:9살, \n성별:여자; \n출력형식:\n영어명사구, 영어명사구",
                        },
                        {
                            "role": "assistant",
                            "content": "A curious nine-year-old boy, surrounded by his friends, standing in front of a treasure map",
                        },
                        {
                            "role": "user",
                            "content": f"너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래 제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n{story_json[story_josn_key[key_index]]}\n캐릭터: \n이름:{name}, \n나이:{age}살, \n성별:{gender}; \n출력형식:\n영어명사구, 영어명사구",
                        },
                    ]
                    """

                    # 무한루프에 빠지는 경우 존재
                    while True:
                        try:
                            image_prompt = make_stroy(message_image, temperature=1)
                            break
                        except:
                            err_msg = traceback.format_exc()
                            print("2", err_msg)

                    story_image[story_josn_key[key_index]] = (
                        image_prompt + f", young {gender}"
                    )
                    print(image_prompt)

                # test
                else:
                    """
                    message_image=[{"role":"system", "content":"특정 상황에 대한 내용이 주어지면 그 상황에 대해 이해하고 해당 상황을 사진으로 표현했을 때의 배경을 영어 명사구로 묘사해라. 이때, 묘사한 결과에 사람 혹은 생명체에 대한 묘사가 존재해서는 안된다. 즉, 배경에 생명체에 대한 묘사가 등장해서는 안된다. 다음은 그 예시이다. 상황: 하지만, 상자를 여는 방법을 모르는 hihi와 친구들은 어떻게 해야 할지 막막해졌어요. 출력형식: A perplexing scene of an unopened box radiating with puzzlement, bereft of any living entities. "},
                           {"role":"user","content":f"상황: {story_json[story_josn_key[key_index]]}"}]

                    # 무한루프에 빠지는 경우 존재
                    while True:
                        try:
                            image_prompt=make_stroy(message_image,temperature=0.75)
                            break
                        except:
                            err_msg = traceback.format_exc()
                            print("2",err_msg)

                    story_image[story_josn_key[key_index]]=image_prompt
                    print(image_prompt)

                    message_image = [
                        {
                            "role": "user",
                            "content": "너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래  제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n한 날, 나현이는 호기심이 많은 소년이었습니다. 학교 과학 수업에서 배운 보물 찾기에 흥미를 느껴 함께 보물을 찾아보자고 친구들에게 제안했어요.\n캐릭터: \n이름:나현, \n나이:9살, \n성별:여자; \n출력형식:\n영어명사구, 영어명사구",
                        },
                        {
                            "role": "assistant",
                            "content": "A curious nine-year-old boy, surrounded by his friends, standing in front of a treasure map",
                        },
                        {
                            "role": "user",
                            "content": f"너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래 제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n{story_json[story_josn_key[key_index]]}\n캐릭터: \n이름:{name}, \n나이:{age}살, \n성별:{gender}; \n출력형식:\n영어명사구, 영어명사구",
                        },
                    ]
                    """
                    message_image = [
                        {
                            "role": "user",
                            "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                        },
                        {
                            "role": "assistant",
                            "content": "(),(),()",
                        },
                        {
                            "role": "user",
                            "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{major}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                        },
                    ]

                    # 무한루프에 빠지는 경우 존재
                    while True:
                        try:
                            image_prompt = make_stroy(message_image, temperature=1)
                            break
                        except:
                            err_msg = traceback.format_exc()
                            print("2", err_msg)

                    story_image[story_josn_key[key_index]] = (
                        image_prompt + f", young {gender}"
                    )
                    print(image_prompt)

            """
            for key in list(story_json.keys()):
                print(story_json[key])
                message_image=[{"role":"system", "content":"특정 상황에 대한 내용이 주어지면 그 상황에 대해 이해하고 해당 상황을 사진으로 표현했을 때의 배경을 영어 명사구로 묘사해라. 이때, 함께 제시되는 캐릭터 설정을 참고해 캐릭터의 이름은 사용하지 않고 성별만 사용해 상황을 묘사해라. 캐릭서 설정: 이름, 나이, 성별; 다음은 한 가지 예시이다. 상황: 한 번은 서아가 엄마와 함께 동물 병원에 갔어요; 캐릭터 설정: 서아, 3살, 여자; 출력형식: A three-year-old girl, standing in front of the hospital;"},
                       {"role":"user","content":f"상황: {story_json[key]}; 캐릭터 설정: {name}, {age}살, {gender}"}]
                       
                # 무한루프에 빠지는 경우 존재
                while True:
                    try:
                        image_prompt=make_stroy(message_image,temperature=0.75)
                        break
                    except:
                        err_msg = traceback.format_exc()
                        print("2",err_msg)
                
                story_image[key]=image_prompt
                print(image_prompt)
            """

        except:
            err_msg = traceback.format_exc()
            print("3", err_msg)
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: check plz!!"
            post_slack(notification)
            print("something went wrong!!")
            return {"statusCode": 500, "body": "chatgpt error!!"}

        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
        table_gpt_story = dynamodb.Table(f"Dy_gpt_story_{env}")
        table_gpt_prompt = dynamodb.Table(f"Dy_gpt_prompt_{env}")
        table_story_summary = dynamodb.Table(f"Dy_story_summary_prod")
        # dynamodb put!!
        try:
            # 스토리
            story_json["user_id"] = user_id
            story_json["time_stamp"] = time_stamp
            temp = table_gpt_story.put_item(Item=story_json)

            # 스토리 상황묘사
            story_image["user_id"] = user_id
            story_image["time_stamp"] = time_stamp
            temp = table_gpt_prompt.put_item(Item=story_image)

            # 책 제목 설정
            query = f"UPDATE Dy_story_event_{env} SET title = '{title}' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
            result = dynamodb_client.execute_statement(Statement=query)

        except:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: dynamodb error!"
            post_slack(notification)
            print("put dynamodb error!!!!")

        # 줄거리 생성
        try:
            story = ""
            for key_index in range(len(story_josn_key)):
                story += " " + story_json[story_josn_key[key_index]]
            print(story)
            message = [
                {
                    "role": "user",
                    "content": "다음 동화를 이해하고 해당 동화에 대한 줄거리를 두 문장으로 작성해줘. \n 동화:\n %(story)s"
                    % {
                        "story": story,
                    },
                }
            ]
            while True:
                try:
                    story_summary = make_stroy(message, temperature=1)
                    break
                except:
                    err_msg = traceback.format_exc()
                    print("2", err_msg)

            print(story_summary)
            story_summary_json = {}
            story_summary_json["user_id"] = user_id
            story_summary_json["time_stamp"] = time_stamp
            story_summary_json["summary"] = story_summary
            temp = table_story_summary.put_item(Item=story_summary_json)

        except:
            print("error occur!!")

        # 퀴즈 생성
        table_story_quiz = dynamodb.Table(f"Dy_story_quiz_prod")

        message = [
            {
                "role": "user",
                "content": "너는 주어진 동화에 대한 퀴즈를 만들어주는 작가 선생님으로, 아이들에게 이야기해주는 톤을 유지하며, 아래의 동화제목, 동화내용을 기반으로 제약사항을 참고하여 아래 출력형식(JSON)에 맞춰 퀴즈를 생성해라. \n 동화제목: %(title)s \n 동화내용: %(story)s \n 제약사항: \n 최대 question 개수: 4개; \n question 개수: 4개; \n choices수: 4개; \n 출력형식:{quiz_title:"
                ",quiz_questions:{[question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:}]}"
                % {
                    "title": title,
                    "story": story,
                },
            }
        ]
        quiz_temp = {}
        quiz_temp["user_id"] = user_id
        quiz_temp["time_stamp"] = time_stamp

        while True:
            try:
                story_quiz = make_stroy(message, temperature=1)
                story_json = json.loads(story_quiz)
                print(story_json["quiz_title"])
                print(story_json["quiz_questions"])
                number = 1
                for question_temp in story_json["quiz_questions"]:
                    question = question_temp["question"]
                    choices = question_temp["choices"]
                    correct_answer = question_temp["correct_answer"]
                    quiz_temp[f"{number}_question"] = question
                    quiz_temp[f"{number}_choices"] = choices
                    quiz_temp[f"{number}_correct_answer"] = correct_answer
                    number += 1
                break
            except:
                err_msg = traceback.format_exc()
                print("2", err_msg)
                notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: quiz fail!!"
                post_slack(notification)
                break
        # print(story_json)
        # print(quiz_temp)
        try:
            temp = table_story_quiz.put_item(Item=quiz_temp)
        except:
            print("dynamodb query error!!")

        # sqs 전송 (SQS_post_midjourney_story)
        try:
            # 최종 처리는 sqs에 연결된 lambda가 진행
            sqs = boto3.resource("sqs", region_name="ap-northeast-2")
            queue = sqs.get_queue_by_name(QueueName=f"SQS_gpt_validation_{env}")
            temp_json = {}
            temp_json["user_id"] = user_id
            temp_json["time_stamp"] = time_stamp

            message_body = json.dumps(temp_json)
            response = queue.send_message(
                MessageBody=message_body,
            )

        except ClientError as error:
            logger.exception("Send Upscale message failed: %s", message_body)
            raise error

        print("good")
        return {"statusCode": 200, "body": "gg"}

    # MVP 2차 버전
    elif version == "2":
        try:
            env = "prod"
            # print(user_id,time_stamp)
            query = f"SELECT * FROM Dy_story_event_{env} where user_id='{user_id}' and time_stamp='{time_stamp}'"
            # print(query)
            result = dynamodb_client.execute_statement(Statement=query)

            mode = result["Items"][0]["mode"]["S"]
        except:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: event_parsing_fail!"
            post_slack(notification)
            print("event_parsing_fail!!!!!")
            return {"statusCode": 200, "body": "..."}

        age = str(result["Items"][0]["age"]["S"])
        gender = result["Items"][0]["gender"]["S"]
        name = result["Items"][0]["name"]["S"]

        # 주제 추천
        if mode == "0":
            major = result["Items"][0]["major"]["S"]
            middle = result["Items"][0]["middle"]["S"]
            sub = result["Items"][0]["sub"]["S"]
            message = [
                {
                    "role": "user",
                    "content": "너는 아이들을 위한 동화 생성하고 이야기해 주는 작가 선생님으로, 아이들에게 이야기해주는 톤을 유지하며, 아래의 캐릭터설정을 기반으로 동화분류와 제약사항을 참고하여 그 구성과 아래 출력형식(JSON)에 맞춰 동화를 작성해라.\n동화분류:\n대분류: %(major)s; 중분류: %(middle)s; 소분류: %(sub)s \n제약사항:\n최대페이지수: 8;\n페이지수: 8;\n페이지의양: 최소 30 tokens;\n제목: 새로운 캐릭터 등장과 함께 소개할수 있는 제목 구성\n대상: 3~6세\n말투: 했어요\n 캐릭터설정: %(name)s, %(age)s살, %(gender)s \n출력형식:{제목:동화의 제목, 1:페이지 내용, 2:페이지 내용, 3:페이지 내용, 4:페이지 내용, 5:페이지 내용, 6:페이지 내용, 7:페이지 내용, 8:페이지 내용}"
                    % {
                        "major": major,
                        "middle": middle,
                        "sub": sub,
                        "name": name,
                        "age": age,
                        "gender": gender,
                    },
                }
            ]

        # 유저 직접 입력
        elif mode == "1":
            background = result["Items"][0]["background"]["S"]
            theme = result["Items"][0]["theme"]["S"]
            message = [
                {
                    "role": "user",
                    "content": "너는 아이들을 위한 동화 생성하고 이야기해 주는 작가 선생님으로, 아이들에게 이야기해주는 톤을 유지하며, 아래의 캐릭터설정을 기반으로 동화설정과 제약사항을 참고하여 그 구성과 아래 출력형식(JSON)에 맞춰 동화를 작성해라.\n동화분류:\n배경: %(background)s; 상황: %(theme)s; \n제약사항:\n최대페이지수: 8;\n페이지수: 8;\n페이지의양: 최소 30 tokens;\n제목: 새로운 캐릭터 등장과 함께 소개할수 있는 제목 구성\n대상: 3~6세\n말투: 했어요. \n캐릭터설정: %(name)s, %(age)s살, %(gender)s \n출력형식:{제목:동화의 제목, 1:페이지 내용, 2:페이지 내용, 3:페이지 내용, 4:페이지 내용, 5:페이지 내용, 6:페이지 내용, 7:페이지 내용, 8:페이지 내용}"
                    % {
                        "background": background,
                        "theme": theme,
                        "name": name,
                        "age": age,
                        "gender": gender,
                    },
                }
            ]

        # json 형식 검사
        temperature = 1
        flag = False
        while temperature > 0.7:
            try:
                story = make_stroy_gpt_4(message, temperature=temperature)
                print(story)
                story_json = json.loads(story)
                if len(list(story_json.keys())) == 9:
                    title = story_json[list(story_json.keys())[0]]
                    print(title)
                    del story_json[list(story_json.keys())[0]]

                    f = True
                    # gpt에서 글이 생성되지 않는 경우 방지...
                    for key in list(story_json.keys()):
                        if len(story_json[key]) == 0:
                            f = False
                    if f:
                        flag = True
                        break
                else:
                    temperature -= 0.1
            except:
                try:
                    check = story.split("{")
                    if len(check[0]) > 1:
                        if len(check) == 2:
                            temp_story = "{" + check[1]
                            print(temp_story)
                            story_json = json.loads(temp_story)
                            try:
                                if len(list(story_json.keys())) == 9:
                                    title = story_json[list(story_json.keys())[0]]
                                    print(title)
                                    del story_json[list(story_json.keys())[0]]

                                    f = True
                                    # gpt에서 글이 생성되지 않는 경우 방지...
                                    for key in list(story_json.keys()):
                                        if len(story_json[key]) == 0:
                                            f = False
                                    if f:
                                        flag = True
                                        break
                            except:
                                pass
                except:
                    print("haha")

                temperature -= 0.1
                err_msg = traceback.format_exc()
                print("1", err_msg)

        if not flag:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: gpt_fail!!"
            post_slack(notification)
            print("gpt fail!!!")
            return {"statusCode": 200, "body": "gg"}

        try:
            story_image = {}

            story_josn_key = list(story_json.keys())

            for key_index in range(len(story_josn_key)):
                print(story_json[story_josn_key[key_index]])

                # 주인공 등장
                if key_index % 2 == 0:
                    # 주제 추천
                    if mode == "0":
                        message_image = [
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                            {
                                "role": "assistant",
                                "content": "(),(),()",
                            },
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{major}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                        ]
                    else:
                        # 유저 입력 동화
                        message_image = [
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                            {
                                "role": "assistant",
                                "content": "(),(),()",
                            },
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{theme}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                        ]

                    """
                    message_image = [
                        {
                            "role": "user",
                            "content": "너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래  제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n한 날, 나현이는 호기심이 많은 소년이었습니다. 학교 과학 수업에서 배운 보물 찾기에 흥미를 느껴 함께 보물을 찾아보자고 친구들에게 제안했어요.\n캐릭터: \n이름:나현, \n나이:9살, \n성별:여자; \n출력형식:\n영어명사구, 영어명사구",
                        },
                        {
                            "role": "assistant",
                            "content": "A curious nine-year-old boy, surrounded by his friends, standing in front of a treasure map",
                        },
                        {
                            "role": "user",
                            "content": f"너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래 제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n{story_json[story_josn_key[key_index]]}\n캐릭터: \n이름:{name}, \n나이:{age}살, \n성별:{gender}; \n출력형식:\n영어명사구, 영어명사구",
                        },
                    ]
                    """

                    # 무한루프에 빠지는 경우 존재
                    while True:
                        try:
                            image_prompt = make_stroy(message_image, temperature=0.85)
                            break
                        except:
                            err_msg = traceback.format_exc()
                            print("2", err_msg)

                    story_image[story_josn_key[key_index]] = (
                        image_prompt + f", young {gender}"
                    )
                    print(image_prompt)

                # test
                else:
                    # 주제 추천
                    if mode == "0":
                        message_image = [
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                            {
                                "role": "assistant",
                                "content": "(),(),()",
                            },
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{major}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                        ]
                    else:
                        # 유저 입력 동화
                        message_image = [
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:\n배경:\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                            {
                                "role": "assistant",
                                "content": "(),(),()",
                            },
                            {
                                "role": "user",
                                "content": f"너는 주어진 동화내용에 대한 삽화를 생성하는 삽화가이다. 주어진 동화내용을 배경을 참고해 이해한 후 이에 어울리는 삽화를 그릴 때 이 삽화를 영어명사구로 아래 제약사항에 맞춰 출력형식으로 묘사해라.\n동화내용:{story_json[story_josn_key[key_index]]}\n배경:{theme}\n제약사항:\n영어로 작성한다.\n삽화를 출력형식에 맞춰 영어명사구로 설명한다. \n캐릭터 이름을 성별로 치환한다.\n영어명사구는 최대 5개의 단어로 이루어진다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n반드시 한 단어 이상의 영어명사구를 작성한다.\n반드시 인칭대명사로만 인물을 지칭한다.\n캐릭터:\n 이름:{name}\n나이:{age}\n성별:{gender}\n출력형식:\n(background),(situation),(emotion)",
                            },
                        ]

                    """
                    message_image = [
                        {
                            "role": "user",
                            "content": "너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래  제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n한 날, 나현이는 호기심이 많은 소년이었습니다. 학교 과학 수업에서 배운 보물 찾기에 흥미를 느껴 함께 보물을 찾아보자고 친구들에게 제안했어요.\n캐릭터: \n이름:나현, \n나이:9살, \n성별:여자; \n출력형식:\n영어명사구, 영어명사구",
                        },
                        {
                            "role": "assistant",
                            "content": "A curious nine-year-old boy, surrounded by his friends, standing in front of a treasure map",
                        },
                        {
                            "role": "user",
                            "content": f"너는 사진을 처음 보여주는 미국 맹인에게 이미지를 설명하는 image descriptor 이다. 아래 상황문장들로 설명되는 하나의 사진이 있을때, 이 사진을 미국 맹인에게 설명하는 영어명사구를 아래 제약사항에 맞춰 출력형식으로 작성해라. \n 제약사항: \n영어로 작성한다. \n상황을 묘사하는 영어 명사구로 표현한다. \n캐릭터 이름을 성별로 치환한다.\n캐릭터의 이름을 사용하지 않고 성별로 표현한다.\n고유명사를 제거한다.\n상황문장: \n{story_json[story_josn_key[key_index]]}\n캐릭터: \n이름:{name}, \n나이:{age}살, \n성별:{gender}; \n출력형식:\n영어명사구, 영어명사구",
                        },
                    ]
                    """

                    # 무한루프에 빠지는 경우 존재
                    while True:
                        try:
                            image_prompt = make_stroy(message_image, temperature=0.85)
                            break
                        except:
                            err_msg = traceback.format_exc()
                            print("2", err_msg)

                    story_image[story_josn_key[key_index]] = (
                        image_prompt + f", young {gender}"
                    )
                    print(image_prompt)

        except:
            err_msg = traceback.format_exc()
            print("3", err_msg)
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: check plz!!"
            post_slack(notification)
            print("something went wrong!!")
            return {"statusCode": 500, "body": "chatgpt error!!"}

        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
        table_gpt_story = dynamodb.Table(f"Dy_gpt_story_{env}")
        table_gpt_prompt = dynamodb.Table(f"Dy_gpt_prompt_{env}")
        table_story_summary = dynamodb.Table(f"Dy_story_summary_prod")
        try:
            # 스토리
            story_json["user_id"] = user_id
            story_json["time_stamp"] = time_stamp
            temp = table_gpt_story.put_item(Item=story_json)

            # 스토리 상황묘사
            story_image["user_id"] = user_id
            story_image["time_stamp"] = time_stamp
            temp = table_gpt_prompt.put_item(Item=story_image)

            # 책 제목 설정
            query = f"UPDATE Dy_story_event_{env} SET title = '{title}' WHERE user_id='{user_id}' and time_stamp='{time_stamp}';"
            result = dynamodb_client.execute_statement(Statement=query)

        except:
            notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: dynamodb error!"
            post_slack(notification)
            print("put dynamodb error!!!!")

        # 줄거리 생성
        try:
            story = ""
            for key_index in range(len(story_josn_key)):
                story += " " + story_json[story_josn_key[key_index]]

            message = [
                {
                    "role": "user",
                    "content": "다음 동화를 이해하고 해당 동화에 대한 줄거리를 두 문장으로 작성해줘. \n 동화:\n %(story)s"
                    % {
                        "story": story,
                    },
                }
            ]
            while True:
                try:
                    story_summary = make_stroy(message, temperature=1)
                    break
                except:
                    err_msg = traceback.format_exc()
                    print("2", err_msg)

            print(story_summary)
            story_summary_json = {}
            story_summary_json["user_id"] = user_id
            story_summary_json["time_stamp"] = time_stamp
            story_summary_json["summary"] = story_summary
            temp = table_story_summary.put_item(Item=story_summary_json)

        except:
            print("error occur!!")

        # 퀴즈 생성
        table_story_quiz = dynamodb.Table(f"Dy_story_quiz_prod")

        message = [
            {
                "role": "user",
                "content": "너는 주어진 동화에 대한 퀴즈를 만들어주는 작가 선생님으로, 아이들에게 이야기해주는 톤을 유지하며, 아래의 동화제목, 동화내용을 기반으로 제약사항을 참고하여 아래 출력형식(JSON)에 맞춰 퀴즈를 생성해라. \n 동화제목: %(title)s \n 동화내용: %(story)s \n 제약사항: \n 최대 question 개수: 4개; \n question 개수: 4개; \n choices수: 4개; \n 출력형식:{quiz_title:"
                ",quiz_questions:{[question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:"
                "},{question:"
                ", choices:"
                ",correct_answer:}]}"
                % {
                    "title": title,
                    "story": story,
                },
            }
        ]
        quiz_temp = {}
        quiz_temp["user_id"] = user_id
        quiz_temp["time_stamp"] = time_stamp

        while True:
            try:
                story_quiz = make_stroy(message, temperature=1)
                story_json = json.loads(story_quiz)
                print(story_json["quiz_title"])
                print(story_json["quiz_questions"])
                number = 1
                for question_temp in story_json["quiz_questions"]:
                    question = question_temp["question"]
                    choices = question_temp["choices"]
                    correct_answer = question_temp["correct_answer"]
                    quiz_temp[f"{number}_question"] = question
                    quiz_temp[f"{number}_choices"] = choices
                    quiz_temp[f"{number}_correct_answer"] = correct_answer
                    number += 1
                break
            except:
                err_msg = traceback.format_exc()
                print("2", err_msg)
                notification = f"from La_post_gpt: user_id:{user_id}, time_stamp:{time_stamp}, reason: quiz fail!!"
                post_slack(notification)
                break
        # print(story_json)
        # print(quiz_temp)
        try:
            temp = table_story_quiz.put_item(Item=quiz_temp)
        except:
            print("dynamodb query error!!")

        # sqs 전송 (SQS_post_midjourney_story)
        try:
            # 최종 처리는 sqs에 연결된 lambda가 진행
            sqs = boto3.resource("sqs", region_name="ap-northeast-2")
            queue = sqs.get_queue_by_name(QueueName=f"SQS_gpt_validation_{env}")
            temp_json = {}
            temp_json["user_id"] = user_id
            temp_json["time_stamp"] = time_stamp

            message_body = json.dumps(temp_json)
            response = queue.send_message(
                MessageBody=message_body,
            )

        except ClientError as error:
            logger.exception("Send Upscale message failed: %s", message_body)
            raise error

        print("good")
        return {"statusCode": 200, "body": "gg"}
