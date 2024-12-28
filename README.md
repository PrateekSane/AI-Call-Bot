Run the following in one terminal

```
ngrok http 5050
```

In another terminal run:

```
uvicorn app:app --host 0.0.0.0 --port 5050 --reload
```

use twilio online dev phone to pretend to be customer service

make sure to modify on twilio console the ngrok address
