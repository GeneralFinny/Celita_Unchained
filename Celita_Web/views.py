from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
from googletrans import Translator
import re
import pickle

import logging

# ... (your other imports) ...

logger = logging.getLogger(__name__)

# Load the saved model
model = load_model('Models/model1.h5')  # Update the model filename accordingly

# Load the tokenizer used during training
with open('tokenizer.pkl', 'rb') as tokenizer_file:
    tokenizer = pickle.load(tokenizer_file)

# Define the maximum sequence length for input and output
maxlen = 50

# Define the str_to_tokens function
def str_to_tokens(sentence):
    words = sentence.lower().split()
    tokens_list = list()
    for word in words:
        tokens_list.append(tokenizer.word_index[word])
    return pad_sequences([tokens_list], maxlen=maxlen, padding='post')

# Define the process_input function
def process_input(user_input):
    user_input = user_input.lower()
    user_input = re.sub('((www\.[^\s]+)|(https?://[^\s]+))', '', user_input)
    user_input = re.sub('@[^\s]+', '', user_input)
    user_input = re.sub('[\s]+', ' ', user_input)
    user_input = re.sub(r'#([^\s]+)', r'\1', user_input)
    user_input = re.sub(r'[\.!:\?\-\'\"\\/]', r'', user_input)
    user_input = user_input.strip('\'"')
    return user_input

# Define the translate_to_cebuano function
def translate_to_cebuano(user_input):
    user_input = process_input(user_input)

    translator = Translator()
    translated_text = translator.translate(user_input, dest='ceb')

    return translated_text.text

# Define the translate_with_model function
def translate_with_model(user_input, max_output_length=50, temperature=0.7):
    try:
        input_sequence = str_to_tokens(user_input)
    except KeyError:
        print(f"Tokenization error for input: {user_input}. Falling back to Google Translate.")
        return translate_to_cebuano(user_input)

    # Initialize the target sequence with a start token
    target_sequence = np.zeros((1, maxlen), dtype=np.int32)
    target_sequence[0, 0] = tokenizer.word_index['start']  # Replace with your start token index

    decoded_translation = ''

    for _ in range(max_output_length):
        predicted_sequence = model.predict([input_sequence, target_sequence])
        predicted_token = predicted_sequence[0, _]

        # Apply temperature sampling to the predicted token probabilities
        predicted_token = np.log(predicted_token) / temperature
        predicted_token = np.exp(predicted_token) / np.sum(np.exp(predicted_token))
        sampled_token_index = np.random.choice(len(predicted_token), p=predicted_token)

        # Convert token index to word
        sampled_word = None
        for word, index in tokenizer.word_index.items():
            if sampled_token_index == index:
                sampled_word = word
                break

        # Exit if the end token is generated or if the output length exceeds maxlen
        if sampled_word == 'end' or len(decoded_translation.split()) > maxlen:
            break

        # Append the sampled word to the decoded translation
        decoded_translation += ' {}'.format(sampled_word)

        # Update the target sequence for the next step
        target_sequence[0, _ + 1] = sampled_token_index

    return decoded_translation.strip()

@require_POST
@csrf_exempt
def translate(request):
    try:
        logger.info("Translation request received.")
        data = json.loads(request.body)
        logger.info(f"Received data: {data}")
        user_input = data['input_text']

        # Check if the input contains only one word
        if len(user_input.split()) == 1:
            translated_text = translate_to_cebuano(user_input)
        else:
            translated_text = translate_with_model(user_input)

        logger.info(f"Translated text: {translated_text}")
        response_data = {'translated_text': translated_text}
        logger.info(f"Sending response data: {response_data}")

        return JsonResponse(response_data)
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error occurred: {error_message}")
        return JsonResponse({'error': error_message})
