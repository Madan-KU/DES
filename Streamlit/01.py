# import the necessary modules
import streamlit as st
import pandas as pd

# Adding titles 

st.title(" Hello, welcome to Ineuron")

# header
st.header("This is a header")

# adding sub headers 
st.subheader("This is a sub header")

Data= {
    "Company": ["google","Apple","Ineuron"],
    "price": ["100","200","300"],
    "Language": ["Python","java","C++"]
}

st.write(Data)

st.write(pd.DataFrame(Data))

## markdown 

st.markdown("""This is a markdown file
# h1 tag 
## h2 tag
### h3 tag """) 


# import streamlit as st
# import pandas as pd 


# normal way with st.write 
st.write("Hello **world**!")

# magic commands 
"Hello **world**!"

# Text elements

# st.header 
st.header('This is a header')

# st.subheader 

st.subheader('This is a subheader')

# st.caption

st.caption('This is a string that explains something above.')

# st.code 

code = '''def hello():
     print("Hello, Streamlit!")'''
st.code(code, language='python')

# st.text 

st.text('This is some text.')

# st.latex 

st.latex(r'''
     a + ar + a r^2 + a r^3 + \cdots + a r^{n-1} =
     \sum_{k=0}^{n-1} ar^k =
     a \left(\frac{1-r^{n}}{1-r}\right)
     ''')

import streamlit as st
import pandas as pd 
import numpy as np

# Dataframe 
df = pd.DataFrame(
    np.random.randn(50, 20),
    columns=('col %d' % i for i in range(20)))

st.dataframe(df)  # Same as st.write(df)

# st.table 

df = pd.DataFrame(
    np.random.randn(10, 5),
    columns=('col %d' % i for i in range(5)))

st.table(df)

# st.metric 

st.metric(label="Temperature", value="70 °F", delta="1.2 °F")


# st.metric looks especially nice in combination with st.columns:

col1, col2, col3 = st.columns(3)
col1.metric("Temperature", "70 °F", "1.2 °F")
col2.metric("Wind", "9 mph", "-8%")
col3.metric("Humidity", "86%", "4%")

# The delta indicator color can also be inverted or turned off 
st.metric(label="Gas price", value=4, delta=-0.5,
     delta_color="inverse")

st.metric(label="Active developers", value=123, delta=123,
     delta_color="off")

# st.json

st.json({
     'foo': 'bar',
     'baz': 'boz',
     'stuff': [
         'stuff 1',
         'stuff 2',
         'stuff 3',
         'stuff 5',
     ],
 })



import numpy as np
import pandas as pd
import streamlit as st

# line chart 

chart_data = pd.DataFrame(
     np.random.randn(20, 3),
     columns=['a', 'b', 'c'])

st.line_chart(chart_data)

# Area Chart 

chart_data = pd.DataFrame(
     np.random.randn(20, 3),
     columns=['a', 'b', 'c'])

st.area_chart(chart_data)

# bar chart 

chart_data = pd.DataFrame(
     np.random.randn(50, 3),
     columns=["a", "b", "c"])

st.bar_chart(chart_data)

# pyplot 

import matplotlib.pyplot as plt
import numpy as np

arr = np.random.normal(1, 1, size=100)
fig, ax = plt.subplots()
ax.hist(arr, bins=20)

st.pyplot(fig)

# plotly chart

import streamlit as st
import plotly.figure_factory as ff
import numpy as np

# Add histogram data
x1 = np.random.randn(200) - 2
x2 = np.random.randn(200)
x3 = np.random.randn(200) + 2

# Group data together
hist_data = [x1, x2, x3]

group_labels = ['Group 1', 'Group 2', 'Group 3']

# Create distplot with custom bin_size
fig = ff.create_distplot(
         hist_data, group_labels, bin_size=[.1, .25, .5])

# Plot!
st.plotly_chart(fig, use_container_width=True)




# pydeck_chart
# Here's a chart using a HexagonLayer and a ScatterplotLayer on top of the light map style:
import pydeck as pdk

df = pd.DataFrame(
    np.random.randn(1000, 2) / [50, 50] + [37.76, -122.4],
    columns=['lat', 'lon'])

st.pydeck_chart(pdk.Deck(
     map_style='mapbox://styles/mapbox/light-v9',
     initial_view_state=pdk.ViewState(
         latitude=37.76,
         longitude=-122.4,
         zoom=11,
         pitch=50,
     ),
     layers=[
         pdk.Layer(
            'HexagonLayer',
            data=df,
            get_position='[lon, lat]',
            radius=200,
            elevation_scale=4,
            elevation_range=[0, 1000],
            pickable=True,
            extruded=True,
         ),
         pdk.Layer(
             'ScatterplotLayer',
             data=df,
             get_position='[lon, lat]',
             get_color='[200, 30, 0, 160]',
             get_radius=200,
         ),
     ],
 ))




# st.graphviz chart


# import streamlit as st
# import graphviz as graphviz

# # you can render the chart from the graph using GraphViz's Dot language:

# # st.graphviz_chart('''
# #     digraph {
# #         run -> intr
# #         intr -> runbl
# #         runbl -> run
# #         run -> kernel
# #         kernel -> zombie
# #         kernel -> sleep
# #         kernel -> runmem
# #         sleep -> swap
# #         swap -> runswap
# #         runswap -> new
# #         runswap -> runmem
# #         new -> runmem
# #         sleep -> runmem
# #     }
# # ''')








# map 

import streamlit as st
import pandas as pd
import numpy as np

df = pd.DataFrame(
     np.random.randn(1000, 2) / [50, 50] + [37.76, -122.4],
     columns=['lat', 'lon'])

st.map(df)



import streamlit as st
import pandas as pd
import numpy as np

# button 
if st.button('Say hello'):
     st.write('Why hello there')
else:
     st.write('Goodbye')

# checkbox 

agree = st.checkbox('I agree')

if agree:
     st.write('Great!')

# radio button 

genre = st.radio(
     "What's your favorite movie genre",
     ('Comedy', 'Drama', 'Documentary'))

if genre == 'Comedy':
     st.write('You selected comedy.')
else:
     st.write("You didn't select comedy.")

# selectbox

option = st.selectbox(
     'How would you like to be contacted?',
     ('Email', 'Home phone', 'Mobile phone'))

st.write('You selected:', option)

# multiselect 

options = st.multiselect(
     'What are your favorite colors',
     ['Green', 'Yellow', 'Red', 'Blue'],
     ['Yellow', 'Red'])

st.write('You selected:', options)

# slider 

age = st.slider('How old are you?', 0, 130, 25)
st.write("I'm ", age, 'years old')

# An Example of a range slider 
values = st.slider(
     'Select a range of values',
     0.0, 100.0, (25.0, 75.0))
st.write('Values:', values)

#  Range Slider 
from datetime import time
appointment = st.slider(
     "Schedule your appointment:",
     value=(time(11, 30), time(12, 45)))
st.write("You're scheduled for:", appointment)

# Datetime Slider 

from datetime import datetime
start_time = st.slider(
     "When do you start?",
     value=datetime(2020, 1, 1, 9, 30),
     format="MM/DD/YY - hh:mm")
st.write("Start time:", start_time)



import streamlit as st

# Adding audio 
audio_file = open('audio.ogg', 'rb')
audio_bytes = audio_file.read()

st.audio(audio_bytes, format='audio/ogg')

# video 

# video_file = open('C:\\Streamlit_demo\\Introduction Video.mp4', 'rb')
# video_bytes = video_file.read()

# st.video(video_bytes)


add_selectbox = st.sidebar.selectbox(
    "How would you like to be contacted?",
    ("Email", "Home phone", "Mobile phone"),
    key="001"
)

# using st.columns 

col1, col2, col3 = st.columns(3)

with col1:
    st.header("A cat")
    st.image("https://static.streamlit.io/examples/cat.jpg")

with col2:
    st.header("A dog")
    st.image("https://static.streamlit.io/examples/dog.jpg")

with col3:
    st.header("An owl")
    st.image("https://static.streamlit.io/examples/owl.jpg")

#you can just call methods directly in the returned objects:

col1, col2 = st.columns([3, 1])
data = np.random.randn(10, 1)

col1.subheader("A wide column with a chart")
col1.line_chart(data)

col2.subheader("A narrow column with the data")
col2.write(data)

# st.expander 

st.line_chart({"data": [1, 5, 2, 6, 2, 1]})

with st.expander("See explanation"):
     st.write("""
         The chart above shows some numbers I picked for you.
         I rolled actual dice for these, so they're *guaranteed* to
         be random.
     """)
     st.image("https://static.streamlit.io/examples/dice.jpg")

# st.container 
# Inserts an invisible container into your app that can be used to hold multiple elements. This allows you to, for example, insert multiple elements into your app out of order.

with st.container():
    st.write("This is inside the container")

    # You can call any Streamlit command, including custom components:
    st.bar_chart(np.random.randn(50, 3))

st.write("This is outside the container")

# Inserting elements out of order

container = st.container()
container.write("This is inside the container")
st.write("This is outside the container")

# Now insert some more in the container
container.write("This is inside too")




import streamlit as st
import time
# example of a progress bar increasing over time:
my_bar = st.progress(0)

for percent_complete in range(100):
     time.sleep(0.1)
     my_bar.progress(percent_complete + 1)

# st.spinner

with st.spinner('Wait for it...'):
    time.sleep(5)
st.success('Done!')

# st.ballons 
st.balloons()

# st.error

st.error('This is an error')

# st.warnings

st.warning('This is a warning')

# st.info 

st.info('This is a purely informational message')

# st.success 

st.success('This is a success message!')

# st.exception

e = RuntimeError('This is an exception of type RuntimeError')
st.exception(e)

import streamlit as st
import pandas as pd
import numpy as np

# st.stop 
# Streamlit will not run any statements after st.stop(). We recommend rendering a message to explain why the 
# script has stopped. When run outside of Streamlit, this will raise an Exception.

name = st.text_input('Name')
if not name:
  st.warning('Please input a name.')
  st.stop()
st.success('Thank you for inputting a name.')

# st.form

# Inserting elements using "with" notation:

with st.form("my_form"):
    st.write("Inside the form")
    slider_val = st.slider("Form slider")
    checkbox_val = st.checkbox("Form checkbox")

    # Every form must have a submit button.
    submitted = st.form_submit_button("Submit")
    if submitted:
        st.write("slider", slider_val, "checkbox", checkbox_val)

st.write("Outside the form")

# Inserting elements out of order:

#form = st.form("my_form")
#form.slider("Inside the form")
#st.slider("Outside the form")

# Now add a submit button to the form:
#form.form_submit_button("Submit")