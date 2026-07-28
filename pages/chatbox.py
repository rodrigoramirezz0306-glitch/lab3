from google import genai
import streamlit as st
from google.genai.errors import ClientError

st.header("Stock Chat Bot")


#!!!!!!!!!SESSION STATE SECTION!!!!!!!!!#


if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []


#Allows us to keep a visual convo history

for message in st.session_state.chat_history:
    with st.chat_message('user'):
        st.write(message)



#API key string goes here; remember to hide it once we upload it to streamlit
key = "AQ.Ab8RN6JJyVKaJXyfibjk4Ew1bvslqk3HnViZAOJq4cKw2G1GyA"

# Initialize client. 
client = genai.Client(api_key=key)




#CHAT PROMPT (  st.chat_input() )

chatPrompt = st.chat_input("Ask me about stocks!")

#if acts as a barrier, it tells python to wait until the user inputs data

if chatPrompt:

    st.session_state.chat_history.append(chatPrompt)
    with st.chat_message("user"):
        st.write(chatPrompt)

#Changed the model repeatly due to errors       
    try:
        response = client.models.generate_content(
            model = "gemini-3.5-flash",
            contents = chatPrompt
            )
        st.session_state.chat_history.append(response.text)
        with st.chat_message("assistant"):
            st.write(response.text)

    except ClientError:
        response1 = "Sorry, you have reached the maximum of 15 calls per minute. Try again later."
        st.session_state.chat_history.append(response1)

        with st.chat_message("assistant"):
            st.write(response1)

                

#Inappropriate Content and/or Safety Blocks + other errors
    except:
        response2 = "Sorry, I am unable to answer your question. Care to try another one?"
        st.session_state.chat_history.append(response2)

        with st.chat_message("user"):
            st.write(response2)




#except Exception as e:
        
#        responsel = f"An error occurred: {e}"
#        st.session_state.chat_history.append(responsel)
#        with st.chat_message("assistant"):
            
#            st.write(responsel)



