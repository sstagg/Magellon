import plotly.graph_objs as go
import re

shifts = []

with open('./23mar23b_a_00038gr_00003sq_v02_00008hl_v01_00002ex_st_Log.txt') as f:
    for line in f:
        match = re.search(r'Add Frame #\d+ with xy shift: (-?\d+\.\d+) (-?\d+\.\d+)', line)
        if match:
            x, y = match.groups()
            shifts.append((float(x), float(y)))



# shifts = [(-1.16500, 1.19500),
#           (-0.75000, 1.51000),
#           (-0.51500, 1.61500),
#           (-0.62500, 1.56500),
#           (-0.39500, 1.49000),
#           (-0.31000, 1.53500),
#           (-0.01000, 1.49500),
#           (0.01500, 1.24500),
#           (0.16500, 1.03500),
#           (-0.10500, 0.90500),
#           (-0.04500, 0.90000),
#           (-0.17500, 0.75500),
#           (-0.14500, 0.75500),
#           (0.06500, 0.57500),
#           (0.08000, 0.67000),
#           (0.15500, 0.54500),
#           (0.23000, 0.53500),
#           (0.27000, 0.58500),
#           (0.21000, 0.47000),
#           (0.37500, 0.37500),
#           (0.34500, 0.25000),
#           (-0.08000, 0.14500),
#           (-0.09000, 0.08000),
#           (0.03000, 0.19000),
#           (0.20500, 0.18000),
#           (0.15000, 0.16000),
#           (0.07500, 0.20500),
#           (0.16000, 0.17500),
#           (-0.15500, 0.16000),
#           (-0.12500, 0.27000),
#           (-0.07500, 0.20500),
#           (-0.08500, 0.22500),
#           (0.13500, 0.33500),
#           (0.15500, 0.25000),
#           (0.02000, 0.14000),
#           (-0.04500, 0.36000),
#           (-0.12000, 0.18500),
#           (0.04500, 0.18500),
#           (-0.12500, 0.21000),
#           (-0.01500, 0.03500),
#           (0.00000, 0.00000),
#           (-0.04000, 0.06000),
#           (0.12000, -0.05000),
#           (-0.06500, 0.02000),
#           (0.01500, 0.12000),
#           (0.08000, 0.13500),
#           (0.03000, 0.26000),
#           (-0.06000, 0.21000),
#           (-0.08500, 0.01500),
#           (0.09500, 0.32500),
#           (0.08000, 0.10500),
#           (-0.14000, 0.02500),
#           (-0.21000, 0.15000),
#           (0.05500, 0.22500),
#           (0.02500, 0.16000)]
# extract x and y coordinates separately using list comprehension
x = [shift[0] for shift in shifts]
y = [shift[1] for shift in shifts]

# scatter plot of all points connected by a 1-pixel line
fig = go.Figure()
fig.add_trace(go.Scatter(x=x, y=y, mode='markers', marker=dict(color='black')))
fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(color='lightblue', dash='dash')))

# set axis limits based on the range of the data
x_range = max(x) - min(x)
y_range = max(y) - min(y)
padding = 0.1  # add 10% padding to the axis limits
fig.update_layout(xaxis_range=[min(x) - x_range*padding, max(x) + x_range*padding],
                  yaxis_range=[min(y) - y_range*padding, max(y) + y_range*padding])

# add horizontal and vertical lines at 0
fig.add_shape(type='line', x0=min(x), y0=0, x1=max(x), y1=0, line=dict(color='black', width=1))
fig.add_shape(type='line', x0=0, y0=min(y), x1=0, y1=max(y), line=dict(color='black', width=1))

# add labels and title
fig.update_layout(xaxis_title='X', yaxis_title='Y', title='Motion Graph2')

# show the plot
fig.show()