import json
import boto3
import requests
from bs4 import BeautifulSoup


from utils import (
    base_url,
    artists,
    display_names,
    get_ssm_parameter,
    get_token
)


dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')


def lambda_handler(event, context):
    """check_ticket Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    try:
        # 空き状況一覧
        artist_available_tickets = {}

        token = get_token(
            get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
            get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
        )

        # まずアーティストでイテレーションする
        for artist_name, artist_id in artists.items():
            # アーティストの空き状況一覧を初期化
            artist_available_tickets[artist_name] = []

            artist_page_url = f"{base_url}/events/artist/{artist_id}"
            artist_res = requests.get(artist_page_url)
            artist_soup = BeautifulSoup(artist_res.text, 'html.parser')

            # アーティストのイベント情報を取得して更にイテレーション
            events = artist_soup.find_all('a', { 'class': 'd-block' })
            for event in events:
                event_url = event.get('href')
                if not event_url:
                    continue

                # event_id = event_url.split('/')[-1]
                event_res = requests.get(f"{base_url}/{event_url}")
                event_soup = BeautifulSoup(event_res.text, 'html.parser')
                # perform-listをすべて取得
                perform_list = event_soup.find_all('div', { 'class': 'perform-list' })
                for perform in perform_list:
                    # 日時
                    perform_date = perform.find('div', { 'class': 'lead' }).text
                    # 会場
                    perform_place = perform.find('p').text
                    # 「購入手続きへ」ボタン（ない場合もある）
                    buy_button = perform.find('button', { 'class': 'btn' })
                    # 「購入手続きへ」ボタンが存在する場合、artist_available_ticketsに日時と会場とURLを追加
                    if buy_button:
                        print('空きあり', artist_name, perform_date, perform_place, f"{base_url}/{event_url}")
                        artist_available_tickets[artist_name].append({
                            'date': perform_date,
                            'place': perform_place,
                            'url': f"{base_url}/{event_url}"
                        })

        # ユーザーに空き状況を通知
        for artist in artist_available_tickets:
            if artist_available_tickets[artist]:
                message = f"{display_names[artist]} のチケットが見つかりました\n"
                for ticket in artist_available_tickets[artist]:
                    message += f"日時：{ticket['date']}\n"
                    message += f"会場：{ticket['place']}\n"
                    message += f"URL：{ticket['url']}"

                # 通知対象のユーザーを取得
                table = dynamodb.Table('TicketBotUsers')
                response = table.query(
                    IndexName='artist-index',
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('artist').eq(artist)
                )
                print('query response:', response)
                items = response.get('Items', [])
                user_list = [item['userId'] for item in items]
                if not user_list:
                    print(f"{artist} の登録ユーザーは見つかりませんでした")
                    continue

                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
                body = {
                    'to': user_list,
                    'messages': [
                        {
                            'type': 'text',
                            'text': message
                        }
                    ]
                }
                response = requests.post(
                    'https://api.line.me/v2/bot/message/multicast',
                    headers=headers,
                    json=body
                )
                response.raise_for_status()  # エラー時に例外を投げる
                print('multicast response:', response.json())
            else:
                print(f"{artist} のチケットは見つかりませんでした")

    except Exception as e:
        # エラーが発生した場合、管理者に通知
        print('Error:', e)
        token = get_token(
            get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
            get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
        )
        admin_line_user_id = get_ssm_parameter('TICKET_ADMIN_LINE_USER_ID')

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        message = {
            'to': admin_line_user_id,
            'messages': [
                {
                    'type': 'text',
                    'text': f'Error occurred in check_ticket: {str(e)}'
                }
            ]
        }
        response = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers=headers,
            json=message
        )
        response.raise_for_status()  # エラー時に例外を投げる
        print('Error notification response:', response.json())

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {'Content-Type': 'application/json'}
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'processed successfully'
        }),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
