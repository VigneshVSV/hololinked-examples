import typing
import datetime
import numpy
from dataclasses import dataclass
import plotly.graph_objects as go
from daqpy.server.remote_parameter import PlotlyFigure


@dataclass 
class Intensity:
    value : numpy.ndarray
    timestamp : str  

    def json(self):
        return {
            'value' : self.value.tolist(),
            'timestamp' : self.timestamp
        }

    @property
    def not_completely_black(self):
        if any(self.value[i] > 0 for i in range(len(self.value))):  
            return True 
        return False
    


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