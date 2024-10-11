# write a function that calls the openai api to generate a response to a given prompt

import openai
import os
import dotenv
import langchain

class Agent:
    def __init__(self, name, address, issue, company):
        dotenv.load_dotenv()
        self.openai = openai.OpenAI()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.system_prompt = self.generate_system_prompt(name, address, issue, company)

    def generate_system_prompt(self, name, address, issue, company):
        default_prompt = f"""
        Your manager is {name} and you are their assistant. 
        you are talking on their behalf to a customer service representative. 
        Your manager's details are:
            Name: {name}
            Address: {address}
            Issue: {issue}
        
        You are talking to a customer service representative from the following company: {company}.
        Your manager is having trouble with the following: {issue}.

        Please try to get the customer service representative the basic information so that 
        they can help your manager with the issue.

        Make sure to only use the information that is provided to you.
        Do not make up any information.
        If you do not know the answer, please say so.
        """

        return default_prompt

    def answer_question(self, sys_prompt, question):
        response = self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        return response.choices[0].message.content

    def check_confidence(self, answer, question, confidence_threshold=0.8):
        confidence_check = self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a confidence checker. Respond with a number between 0 and 1 representing the confidence level of the given answer to the question."},
                {"role": "user", "content": f"Question: {question}\nAnswer: {answer}\n\nHow confident are you in this answer? Respond with a number between 0 and 1."}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        try:
            confidence = float(confidence_check.choices[0].message.content.strip())
        except ValueError:
            confidence = 0
        
        if confidence < confidence_threshold:
            return False

        return True

    def notify_user(self, message):
        print(f"Notification: {message}")
        print("I have done the following")
        print("Please review the notification and take appropriate action.")
    
    def handle_dummy_situation(self):
        # Define a dummy situation
        manager_name = "Jane Smith"
        manager_address = "456 Oak St, Somewhere, USA"
        issue = "resetting the account password"
        company_name = "TechCorp Inc."
        question = "How can I reset my account password?"

        # Generate system prompt
        sys_prompt = self.generate_system_prompt(manager_name, manager_address, issue, company_name)

        # Get the answer
        answer = self.answer_question(sys_prompt, question)

        # Check confidence
        is_confident = self.check_confidence(answer, question)

        if is_confident:
            self.notify_user(f"Confident answer provided: {answer}")
        else:
            # needs to loop until the solution is reached or not confident
            pass

        return answer, is_confident


agent = Agent()
agent.handle_dummy_situation()