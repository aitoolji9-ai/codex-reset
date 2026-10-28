"""사용할 메신저/API에 맞게 send 함수만 수정하세요. 기본은 JSON 화면 출력입니다."""
import json


def send(notification):
    """알림을 전달합니다.

    notification['text']: 한국시간·출처가 포함된 메시지
    notification['id'], ['phase']: 중복 확인용 식별자
    notification['event']: 원본에서 정규화한 시각·종류 등

    사용자 발송 코드로 교체할 때:
    - 인증정보·수신 대상은 자신의 로컬 설정에서 읽으세요.
    - API의 성공 응답을 확인한 뒤에만 정상 반환하세요.
    - 실패/결과 불명확 시 예외를 발생시키세요. 자동 재발송은 차단됩니다.
    - 요청에 시간 제한을 두세요. 외부 API가 idempotency key를 지원하면
      id + phase를 키로 사용할 수 있습니다.
    """
    print(json.dumps(notification, ensure_ascii=False), flush=True)
