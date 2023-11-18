import plotly.graph_objects as go
from daqpy.server.remote_parameter import PlotlyFigure


spectrum_plot : go.Figure = PlotlyFigure(
        go.Figure(
            data = [
                go.Scatter(
                        mode = 'lines',
                        name = 'last measured spectrum',           
                    )
                ],
            layout = go.Layout(
                autosize = True,
                width = 800, 
                height = 800 * (9/16),
                title = "Spectrum",
                xaxis = dict( title = "Wavelength (nm)" ),
                yaxis = dict( title = "Intensity (Arbitrary Units)" ) 
                # grid  = dict( columns = 10, rows = 10)           
        )),
        data_sources={
            "data[0].y" : "value"
        },
        update_event_name='data-measured'
    ) # type: ignore