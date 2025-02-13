from project.dash_app.dash_app import Dash, html, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px

# Incorporate data
df = pd.read_csv('dashboard.csv')


year_min, year_max = df['Year'].min(), df['Year'].max()
month_min, month_max = df['Month'].min(), df['Month'].max()

# Initialize the app
app = Dash()

# App layout
app.layout = html.Div([
    html.Div(children='Dashboard with Data, Graph, and Controls'),
    html.Hr(),
    html.Label('Select Year Range:'),
    dcc.RangeSlider(
        min=year_min,
        max=year_max,
        step=1,
        marks={year: str(year) for year in range(year_min, year_max + 1)},
        value=[year_min, year_max], 
        id='year-slider'
    ),
    
    html.Label('Select Month Range:'),
    dcc.RangeSlider(
        min=month_min,
        max=month_max,
        step=1,
        marks={month: str(month) for month in range(month_min, month_max + 1)},
        value=[month_min, month_max],  
        id='month-slider'
    ),
    
    dcc.RadioItems(
        options=['Region', 'Area', 'Dwelling_Type'],
        value='Region',
        id='controls-and-radio-item'
    ),
    dash_table.DataTable(data=df.to_dict('records'), page_size=10, id='data-table'),
    dcc.Graph(figure={}, id='controls-and-graph'),
])

# Add controls to build the interaction
@callback(
    Output(component_id='controls-and-graph', component_property='figure'),
    Output(component_id='data-table', component_property='data'),
    Input(component_id='year-slider', component_property='value'),
    Input(component_id='month-slider', component_property='value'),
    Input(component_id='controls-and-radio-item', component_property='value')
)
def update_graph_and_table(year_range, month_range, col_chosen):
   
    filtered_df = df[(df['Year'] >= year_range[0]) & (df['Year'] <= year_range[1]) &
                     (df['Month'] >= month_range[0]) & (df['Month'] <= month_range[1])]

   
    fig = px.histogram(
        filtered_df, 
        x=col_chosen, 
        y='kwh_per_acc', 
        histfunc='avg'
    )
    fig.update_layout(
        title="Average kWh Consumption by Chosen Category",
        xaxis_title=col_chosen,
        yaxis_title="Average kWh per Account",
        xaxis=dict(tickmode='linear'),
    )
    fig.update_traces(marker_line_width=1, marker_line_color='black', opacity=0.75)
    
   
    table_data = filtered_df.to_dict('records')
    
    return fig, table_data

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
