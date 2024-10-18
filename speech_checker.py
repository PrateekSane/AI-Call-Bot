import os
import dotenv
from openai import OpenAI

FLASK_ADDRESS = os.getenv('FLASK_ADDRESS')

dotenv.load_dotenv('env/.env')

def is_hold_message(speech_result: str):
    if not speech_result:
        # if silence or if the music doesn't have speech
        return False

    system_prompt = """
        You are an AI assistant that determines if a 
        given text from a phone call is talking to a 
        customer service agent or is just an automated message.
        """

    user_prompt = f"""
        Is the following text likely to be human speech? 
        Say 'yes' if it is human speech and it is not an automated message.
        Say 'no' if it is song lyrics or is an automated message.
        If it is not directly talking to a human, say 'no'.
        Respond with only 'yes' or 'no': '{speech_result}'
        """

    openai_response = call_llm(system_prompt, user_prompt)
    #print(openai_response)
    is_human = openai_response.choices[0].message.content.strip().lower() == 'yes'

    return not is_human


def call_llm(system_prompt: str, user_prompt: str):
    """Call OpenAI API to determine if the speech is human"""
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response


if __name__ == "__main__":
    print(is_hold_message("This is Joe from T-Mobile. How can I help you?"))
    print(is_hold_message("Hi sorry to keep you waiting. Someone will be with you shortly."))
    print(is_hold_message("Hi sorry to keep you waiting. Someone will be with you shortly."))
    print(is_hold_message("I cant stop, who going stop me now"))
