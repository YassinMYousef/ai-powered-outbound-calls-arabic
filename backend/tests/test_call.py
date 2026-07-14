
from app.telephony.client import place_call

TEST_NUMBER = "+201091894094"

if __name__ == "__main__":
    call_sid = place_call(to_number=TEST_NUMBER, call_id=1)
    print(f"Call placed! SID: {call_sid}")
