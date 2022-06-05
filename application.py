# Serve model as a flask application

import pickle
from flask import Flask, request, render_template
import pandas as pd
from predict import data_transform, predict, parse_request

from bokeh.tile_providers import get_provider, Vendors
from bokeh.palettes import Category20c
from bokeh.transform import linear_cmap
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import ColorBar, NumeralTickFormatter
from bokeh.embed import components
from bokeh.resources import CDN
from bokeh.palettes import RdBu

from viz_FilterbyText.pipeline_new_1 import viz_key_df
from viz_FilterbyText.pipeline_new import visualize_count, visualize_price, donut

model = None
df = None
application = Flask(__name__)


def select(df_selected, attributes, ranges):
    assert isinstance(df_selected, pd.DataFrame)
    assert isinstance(attributes, list)
    assert isinstance(ranges, list)
    df_selected = df_selected.copy(deep = True)
    for i, attribute in enumerate(attributes):
        if isinstance(ranges[i], list):
            df_selected = df_selected[df_selected[attribute].isin(ranges[i])]
        else:
            df_selected = df_selected[df_selected[attribute] > ranges[i]]

    return df_selected


def get_ng_dict(df):
    ng_dict = {}
    for _, row in df.iterrows():
        ng = row['neighbourhood_group']
        if ng not in ng_dict.keys():
            ng_dict[ng] = set()
        ng_dict[ng].add(row['neighbourhood'])

    for key, val in ng_dict.items():
        ng_dict[key] = list(val)
    return ng_dict


def load_model():
    global model
    # model variable refers to the global variable
    with open('model.pkl', 'rb') as f:
        model = pickle.load(f)


def get_pd_df(path):
    return pd.read_csv(path)


def parse_price_range(priceRangeStr):
    loStr, hiStr = priceRangeStr.split('-')
    if hiStr == '':
        hiStr = '20000'
    if loStr == '':
        loStr = '0'
    priceRangeList = list(range(int(loStr), int(hiStr)))
    return priceRangeList


def select_from_request(df_selected, result, notfound = False):
    global df
    attributes = []
    ranges = []

    roomTypeList = result.getlist('roomType')
    if roomTypeList != []:
        attributes.append('room_type')
        ranges.append(roomTypeList)

    neighbourhoodGroupList = result.getlist('neighbourhoodGroup')
    if neighbourhoodGroupList != []:
        attributes.append('neighbourhood_group')
        ranges.append(neighbourhoodGroupList)
        
        
        
    
    neighbourhoodList = result.getlist('neighbourhood')
    if neighbourhoodList != []:
        attributes.append('neighbourhood')
        ranges.append(neighbourhoodList)
    if notfound: 
        return select(df, attributes, ranges)

    priceRange = '-'
    min_price = result.get('minPrice')
    max_price = result.get('maxPrice')
    if min_price or max_price:
        if min_price:
            priceRange = min_price + priceRange
        else:
            priceRange = '0' + priceRange
        if max_price:
            priceRange = priceRange + max_price

        attributes.append('price')
        ranges.append(parse_price_range(priceRange))


    min_nights = result.get('minNight')
    if min_nights:
        attributes.append('minimum_nights')
        ranges.append(int(min_nights))

    min_reviews = result.get('minReview')
    if min_reviews:
        attributes.append('number_of_reviews')
        ranges.append(int(min_reviews))
        
    return select(df_selected, attributes, ranges)

def plot_bokeh_map_new(df_new):

    room_list = ['bedroom', 'bedrooms', 'bed',
                 'beds', 'bdrs', 'bdr', 'room', 'rooms',
                 'apt','apartment','studio','loft','townhouse',
                 'bath','baths']
    fs = df_new.copy()

    return viz_key_df(room_list, fs)
 


@application.route('/actual_app', methods=['POST', 'GET'])
def actual_app():
    col_to_show = ['name', 'host_name', 'room_type', 'neighbourhood_group',
                   'neighbourhood',
                   'minimum_nights', 'number_of_reviews', "price"]
    global df
    df = get_pd_df('./data/final_dataframe.csv')

    df_selected = df.copy(deep = True).drop_duplicates(col_to_show).reset_index(drop=True)
    roomTypeSet = set(sorted(set(df['room_type'])))
    neighbourhoodGroupSet = set(sorted(set(df['neighbourhood_group'])))
    neighbourhoodSet = set(sorted(set(df['neighbourhood'])))

    anchor = "top"

    
    ng_dict = get_ng_dict(df)
    msg_pred = str(len(df_selected)) + " records found based on given inputs, Average Price is: $" + str(round(df_selected["price"].mean(), 1)) + ", Median Price is: $" + str(round(df_selected["price"].median(), 1)) + ", displaying top 20 cheapest offerings: "
    # select data according to the submitted form
    
    if request.method == 'POST':
        anchor = "finder"
        df_selected = select_from_request(df_selected, request.form).drop_duplicates(col_to_show).reset_index(drop=True)
        
        if len(df_selected) == 0:
            encoded_input = data_transform(df, request.form)
            price_predicted = predict('model.pkl', encoded_input)
            msg_pred = "We have no available record that match the searching input, but our model recommands a reasonable price based on the market trend" 
            msg_pred = msg_pred + " for the given inputs is: " + "$" + str(price_predicted) + ". " 
            
        elif len(df_selected) < 20: 
            encoded_input = data_transform(df, request.form)
            price_predicted = predict('model.pkl', encoded_input)
            msg_pred = "Less than 20 records found based on the inputs, which may not be representative of the market. Based on our model, a resonable price recommended for the given inputs is: " 
            msg_pred = msg_pred + "$" + str(price_predicted) + ". " 
            
            msg_pred = msg_pred + " \n And the available listings found based on the inputs are: "   
        
        else: 
            msg_pred = str(len(df_selected)) + " records found based on given inputs, Average Price is: $" + str(round(df_selected["price"].mean(), 1)) + ", Median Price is: $" + str(round(df_selected["price"].median(), 1)) + ", displaying top 20 cheapest offerings: "       
    
    # if len(df_selected) == 0: 
    #     df = get_pd_df('./data/final_dataframe.csv')  # No result found, use the closest matches instead 
    #     df_selected = select_from_request(df_selected, request.form, notfound = True).drop_duplicates(col_to_show).reset_index(drop=True)
            
    for i in ng_dict.keys(): 
        ng_dict[i] = list(sorted(ng_dict[i]))
    
    if (df_selected.empty):
        script1 = script1_count = "No result was found given the inputs. " 
        
        div1 = cdn_js = div1_count = cdn_js_count = script1_price = div1_price = cdn_js_price = "" 
    else:
        script1, div1, cdn_js = plot_bokeh_map_new(df_selected)
        script1_count, div1_count, cdn_js_count = visualize_count(df_selected)
        script1_price, div1_price, cdn_js_price = visualize_price(df_selected)
    
    img = donut(df_selected)

    if len(df_selected) >= 20: 
        df_selected = df_selected.head(20)
    if len(df_selected) != 0: 
        tables_shown = [df_selected[col_to_show].rename({"name": "Title", "host_name": "Host", "neighbourhood_group": "Region", "neighbourhood": "Neighbourhood", "room_type": "Room Type", "minimum_nights": "Minimum Nights", "number_of_reviews": "Number of Reviews", "price": "Price Per Day"}, axis = 1).to_html(classes='data', header='true')]
    else: 
        tables_shown = "" 
    return render_template('actual_app.html', anchor=anchor, request_form=request.form,
                           selected_RT = request.form.getlist('roomType'),
                           selected_NG = request.form.getlist('neighbourhoodGroup'),
                           selected_NEI = request.form.get('neighbourhood'),   
                           tables = tables_shown, 
                           roomTypeSet = sorted(roomTypeSet),
                           neighbourhoodGroupSet = sorted(neighbourhoodGroupSet),
                           neighbourhoodSet = neighbourhoodSet, ng_dict = ng_dict,
                           script1=script1, div1=div1, cdn_js=cdn_js, msg_pred=msg_pred,
                           script1_count=script1_count, div1_count=div1_count, cdn_js_count=cdn_js_count,
                           script1_price=script1_price, div1_price=div1_price, cdn_js_price=cdn_js_price,
                           img = img)
@application.route('/', methods=['POST', 'GET'])
def home_endpoint():

    return render_template('index.html')
if __name__ == '__main__':
    load_model()  # load model at the beginning once only
    application.run(host='0.0.0.0', port=5000, debug = True, use_reloader = False)

