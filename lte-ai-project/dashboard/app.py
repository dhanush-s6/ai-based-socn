"""
Flask/Dash Dashboard for LTE-AI SON Cellular Network

Real-time monitoring and control interface with:
- Live KPI graphs for all 6 base stations
- Anomaly detection indicators
- Error injection UI
- WebSocket communication with NS3 simulator
"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import threading
import sys

# Add parent directory to imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_manager import get_config
from simulator.error_definitions import get_all_error_types
from simulator.error_injector import get_error_injector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Dashboard")

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "LTE-AI SON Network Control"

# Color scheme
COLOR_NORMAL = "#00FF00"
COLOR_WARNING = "#FFFF00"
COLOR_CRITICAL = "#FF0000"
COLOR_DARK = "#1a1a1a"
COLOR_LIGHT = "#f0f0f0"

# Global data store
kpi_cache = {f"enb_{i}": {"times": [], "data": {}} for i in range(6)}
error_injector = get_error_injector()


def load_kpi_data():
    """Load latest KPI data from CSV."""
    # Try both possible paths
    possible_paths = [
        Path("~/Desktop/ns-3-dev/city_kpi_dataset.csv"),
        Path(get_config("simulator.kpi_output_csv", "dataset/city_kpi_dataset.csv"))
    ]
    
    kpi_path = None
    for path in possible_paths:
        if path.exists():
            kpi_path = path
            break
    
    if not kpi_path:
        logger.warning(f"KPI file not found at any location")
        return None
    
    try:
        df = pd.read_csv(kpi_path)
        # Load ALL data (no limit) for full visualization
        logger.info(f"Loaded {len(df)} data points from {kpi_path}")
        return df
    except Exception as e:
        logger.error(f"Error loading KPI data: {e}")
        return None


def load_ai_decisions():
    """Load latest AI decisions from log file."""
    log_file = Path("ai_decisions.log")
    
    if not log_file.exists():
        return html.Div("Waiting for AI decisions...", style={"color": "#999"})
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return html.Div("No decisions yet", style={"color": "#999"})
        
        # Parse last 10 decisions (most recent first)
        import json
        decisions = []
        for line in lines[-10:][::-1]:  # Reverse to show newest first
            try:
                entry = json.loads(line.strip())
                timestamp = entry.get("timestamp", "").split("T")[1][:8]  # HH:MM:SS
                anomaly = entry.get("overall_anomaly_score", 0)
                cells = entry.get("cells", [])
                
                # Format cell actions
                actions = []
                lb_hints = []
                for cell in cells:
                    action = cell.get("action", 0)
                    proposed = cell.get("proposed_action", action)
                    validated = cell.get("validated_action", action)
                    reason = cell.get("stability_reason", "Accepted")
                    lb_reco = cell.get("load_balance_recommendation", "BALANCE")
                    lb_score = float(cell.get("load_balance_score", 0.5))
                    ho_target = cell.get("handover_target")
                    action_names = {0: "Balance", 1: "PowerUp", 2: "PowerDn", 3: "Handover"}
                    actions.append(
                        f"eNB{cell.get('cell_id', 0)+1}:{action_names.get(proposed, '?')}->{action_names.get(validated, '?')}"
                    )
                    if lb_reco != "BALANCE" or lb_score < 0.70 or ho_target is not None:
                        target_txt = f"->eNB{ho_target}" if ho_target is not None else ""
                        lb_hints.append(
                            f"eNB{cell.get('cell_id', 0)+1}:{lb_reco}{target_txt} (score:{lb_score:.2f})"
                        )
                
                decision_text = (
                    f"[{timestamp}] Anomaly:{anomaly:.2f} | Actions: {', '.join(actions)}"
                    f" | Reason:{reason}"
                )
                if lb_hints:
                    decision_text += f" | LB: {'; '.join(lb_hints)}"
                decisions.append(html.Div(decision_text, style={"padding": "5px", "borderBottom": "1px solid #eee", "fontFamily": "monospace", "fontSize": "11px"}))
            except json.JSONDecodeError:
                continue
        
        return html.Div(decisions) if decisions else html.Div("Parsing decisions...", style={"color": "#999"})
    
    except Exception as e:
        logger.error(f"Error loading AI decisions: {e}")
        return html.Div(f"Error: {str(e)}", style={"color": "#e74c3c", "fontSize": "11px"})


def create_metric_card(enb_id: int, metric_name: str, value: float, threshold: float = None):
    """Create a metric display card."""
    # Determine color based on value and threshold
    if threshold:
        color = COLOR_CRITICAL if value > threshold else COLOR_NORMAL
    else:
        color = COLOR_NORMAL
    
    return html.Div([
        html.Div([
            html.H6(f"eNB{enb_id} {metric_name}", style={"margin": "0 0 5px 0"}),
            html.H3(f"{value:.2f}", style={"margin": "5px 0", "color": color})
        ], style={
            "padding": "15px",
            "border": f"2px solid {color}",
            "border-radius": "5px",
            "background-color": "#f9f9f9"
        })
    ])


def create_app_layout():
    """Create the dashboard layout."""
    return html.Div([
        # Header
        html.Div([
            html.H1("LTE-AI SON Network Control Panel", style={"margin": "0"}),
            html.P("Real-time monitoring with AI predictions and error injection", 
                  style={"margin": "5px 0 0 0", "color": "#888"})
        ], style={
            "padding": "20px",
            "background-color": "#2c3e50",
            "color": "white",
            "marginBottom": "20px"
        }),
        
        dcc.Interval(id='interval-component', interval=1000, n_intervals=0),
        dcc.Store(id='error-store', data={}),
        
        html.Div([
            # Left sidebar - Control Panel
            html.Div([
                html.H3("Error Injection", style={"marginBottom": "15px"}),
                
                html.Label("Error Type:"),
                dcc.Dropdown(
                    id="error-type-dropdown",
                    options=[{"label": e.replace("_", " ").title(), "value": e} 
                            for e in get_all_error_types()],
                    value="congestion",
                    style={"marginBottom": "10px"}
                ),
                
                html.Label("Target Cell:"),
                dcc.Dropdown(
                    id="cell-id-dropdown",
                    options=[{"label": f"eNB{i+1}", "value": i} for i in range(6)],
                    value=0,
                    style={"marginBottom": "10px"}
                ),
                
                html.Label("Severity (0-1):"),
                html.Div([
                    dcc.Slider(
                        id="severity-slider",
                        min=0, max=1, step=0.1, value=0.5,
                        marks={i/10: f"{i/10}" for i in range(0, 11, 2)}
                    )
                ], style={"marginBottom": "10px"}),
                
                html.Label("Duration (seconds):"),
                html.Div([
                    dcc.Slider(
                        id="duration-slider",
                        min=5, max=300, step=5, value=30,
                        marks={i: str(i) for i in range(5, 301, 30)}
                    )
                ], style={"marginBottom": "15px"}),
                
                html.Button(
                    "Inject Error",
                    id="inject-button",
                    n_clicks=0,
                    style={
                        "width": "100%",
                        "padding": "10px",
                        "background-color": "#e74c3c",
                        "color": "white",
                        "border": "none",
                        "border-radius": "5px",
                        "fontWeight": "bold",
                        "cursor": "pointer"
                    }
                ),
                
                html.Div(id="injection-output", style={"marginTop": "15px"}),
                
                html.Hr(style={"margin": "20px 0"}),
                
                html.H3("eNB Control", style={"marginBottom": "15px"}),
                html.Div([
                    html.Label("Select eNB:"),
                    dcc.Dropdown(
                        id="enb-control-dropdown",
                        options=[{"label": f"eNB{i+1}", "value": i} for i in range(6)],
                        value=0,
                        style={"marginBottom": "10px"}
                    ),
                    html.Div([
                        html.Button(
                            "START",
                            id="start-enb-button",
                            n_clicks=0,
                            style={
                                "width": "48%",
                                "padding": "10px",
                                "background-color": "#27ae60",
                                "color": "white",
                                "border": "none",
                                "border-radius": "5px",
                                "fontWeight": "bold",
                                "cursor": "pointer",
                                "marginRight": "2%"
                            }
                        ),
                        html.Button(
                            "STOP",
                            id="stop-enb-button",
                            n_clicks=0,
                            style={
                                "width": "48%",
                                "padding": "10px",
                                "background-color": "#e74c3c",
                                "color": "white",
                                "border": "none",
                                "border-radius": "5px",
                                "fontWeight": "bold",
                                "cursor": "pointer"
                            }
                        )
                    ], style={"display": "flex", "gap": "5px", "marginBottom": "10px"}),
                    html.Button(
                        "AI Action",
                        id="ai-action-button",
                        n_clicks=0,
                        style={
                            "width": "100%",
                            "padding": "10px",
                            "background-color": "#2980b9",
                            "color": "white",
                            "border": "none",
                            "border-radius": "5px",
                            "fontWeight": "bold",
                            "cursor": "pointer",
                            "marginBottom": "10px"
                        }
                    ),
                    html.Div(id="enb-control-output", style={
                        "padding": "10px",
                        "background-color": "#ecf0f1",
                        "borderRadius": "5px",
                        "fontSize": "12px",
                        "minHeight": "30px"
                    })
                ], style={"padding": "10px", "background-color": "white", "borderRadius": "5px"}),
                
                html.Hr(style={"margin": "20px 0"}),
                
                html.H3("System Status", style={"marginBottom": "15px"}),
                html.Div(id="system-status", style={
                    "padding": "10px",
                    "background-color": "#ecf0f1",
                    "borderRadius": "5px",
                    "fontFamily": "monospace",
                    "fontSize": "12px"
                })
                
            ], style={
                "width": "25%",
                "display": "inline-block",
                "padding": "20px",
                "background-color": "#ecf0f1",
                "verticalAlign": "top",
                "borderRight": "2px solid #bdc3c7",
                "height": "100vh",
                "overflowY": "auto",
                "boxSizing": "border-box"
            }),
            
            # Main content area
            html.Div([
                # Real-time metrics grid
                html.Div([
                    html.H2("Real-Time KPI Metrics"),
                    html.Div(id="metrics-grid", style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(3, 1fr)",
                        "gap": "15px",
                        "marginBottom": "30px"
                    })
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),
                
                # Throughput graph
                html.Div([
                    html.H3("Throughput (Mbps)"),
                    dcc.Graph(id="throughput-graph")
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),
                
                # Delay graph
                html.Div([
                    html.H3("Delay (ms)"),
                    dcc.Graph(id="delay-graph")
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),
                
                # Packet Loss graph
                html.Div([
                    html.H3("Packet Loss (%)"),
                    dcc.Graph(id="loss-graph")
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),

                # Load-balance score graph
                html.Div([
                    html.H3("Load Balancing Score"),
                    dcc.Graph(id="load-balance-graph")
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),
                
                # SINR/RSRP graphs
                html.Div([
                    html.Div([
                        html.H3("SINR (dB)"),
                        dcc.Graph(id="sinr-graph")
                    ], style={"display": "inline-block", "width": "48%", "marginRight": "4%"}),
                    
                    html.Div([
                        html.H3("RSRP (dBm)"),
                        dcc.Graph(id="rsrp-graph")
                    ], style={"display": "inline-block", "width": "48%"})
                ], style={"padding": "20px", "background-color": "white", "marginBottom": "20px"}),
                
                # AI Actions and anomalies
                html.Div([
                    html.H3("AI Decision Log"),
                    html.Div(id="ai-log", style={
                        "height": "200px",
                        "overflowY": "auto",
                        "padding": "10px",
                        "background-color": "#f5f5f5",
                        "border": "1px solid #ddd",
                        "borderRadius": "5px",
                        "fontFamily": "monospace",
                        "fontSize": "12px"
                    })
                ], style={"padding": "20px", "background-color": "white"})
                
            ], style={
                "width": "75%",
                "display": "inline-block",
                "padding": "0",
                "verticalAlign": "top",
                "boxSizing": "border-box",
                "overflowY": "auto",
                "height": "100vh"
            })
            
        ], style={"display": "flex", "height": "100vh", "margin": "0", "padding": "0"})
        
    ], style={"margin": "0", "padding": "0", "fontFamily": "Arial, sans-serif"})


app.layout = create_app_layout()


# Callbacks
@app.callback(
    [Output("throughput-graph", "figure"),
     Output("delay-graph", "figure"),
     Output("loss-graph", "figure"),
    Output("load-balance-graph", "figure"),
     Output("sinr-graph", "figure"),
     Output("rsrp-graph", "figure"),
     Output("metrics-grid", "children"),
     Output("system-status", "children"),
     Output("ai-log", "children")],
    [Input("interval-component", "n_intervals")],
    prevent_initial_call=False
)
def update_graphs(n):
    """Update all graphs with latest data."""
    df = load_kpi_data()
    
    if df is None or len(df) == 0:
        empty_fig = go.Figure().add_annotation(text="No data available")
        empty_fig.update_layout(height=400)
        return [empty_fig] * 6 + [html.Div("No data")] + ["Loading..."] + [html.Div("Waiting for AI decisions...")]
    
    # Column mapping from CSV headers to metric names
    col_mapping = {
        "throughput": "Th_ENB",
        "delay": "Delay_ENB",
        "loss": "Loss_ENB",
        "sinr": "SINR_ENB",
        "rsrp": "RSRP_ENB"
    }
    
    # Get time axis (convert to seconds if needed)
    time_axis = df["Time"].values if "Time" in df.columns else np.arange(len(df))
    
    # Create figures for each metric
    figures = []
    metrics = ["throughput", "delay", "loss", "sinr", "rsrp"]
    
    for metric in metrics:
        fig = go.Figure()
        csv_prefix = col_mapping[metric]
        
        for enb_id in range(1, 7):  # eNB numbering starts at 1
            col_name = f"{csv_prefix}{enb_id}"
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=time_axis,
                    y=df[col_name],
                    mode='lines',
                    name=f"eNB{enb_id}",
                    line=dict(width=2)
                ))
        
        fig.update_layout(
            height=400,
            hovermode='x unified',
            margin=dict(l=50, r=20, t=20, b=50),
            xaxis_title="Time (s)",
            yaxis_title=metric.capitalize(),
            template="plotly_dark" if len(df) > 500 else "plotly"
        )
        figures.append(fig)

    # Explicit load-balancing score graph (0-1 score and imbalance trend)
    lb_fig = go.Figure()
    load_cols = [c for c in df.columns if c.startswith("Load_ENB")]
    lb_score_series = []
    lb_imbalance_series = []

    if load_cols:
        for _, row in df.iterrows():
            loads = row[load_cols].astype(float).values
            if len(loads) > 0:
                std_load = float(np.std(loads))
                imbalance = float(np.max(loads) - np.min(loads))
                score = max(0.0, min(1.0, 1.0 - (std_load / 0.5)))
            else:
                score = 0.0
                imbalance = 0.0
            lb_score_series.append(score)
            lb_imbalance_series.append(imbalance)

        lb_fig.add_trace(go.Scatter(
            x=time_axis,
            y=lb_score_series,
            mode='lines',
            name='Balance Score (higher is better)',
            line=dict(width=3, color='#27ae60')
        ))

        lb_fig.add_trace(go.Scatter(
            x=time_axis,
            y=lb_imbalance_series,
            mode='lines',
            name='Load Imbalance',
            line=dict(width=2, color='#e74c3c', dash='dash')
        ))

    lb_fig.update_layout(
        height=350,
        hovermode='x unified',
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis_title="Time (s)",
        yaxis_title="Score / Imbalance",
        yaxis=dict(range=[0, 1.05])
    )
    
    # Create metrics cards - one row per eNB with all 4 metrics
    cards = []
    if len(df) > 0:
        latest = df.iloc[-1]
        col_mapping = {
            "Throughput": "Th_ENB",
            "Delay": "Delay_ENB",
            "Loss": "Loss_ENB",
            "UE Count": "UE_ENB"
        }
        
        # Create one row per eNB (1-6)
        for enb_id in range(1, 7):
            row_metrics = []
            
            # Show all 4 metrics for this eNB in a row
            for metric_name, csv_prefix in col_mapping.items():
                col_name = f"{csv_prefix}{enb_id}"
                if col_name in latest.index:
                    value = latest[col_name]
                    
                    # Create metric box
                    metric_box = html.Div([
                        html.Div(metric_name, style={"fontSize": "12px", "fontWeight": "bold", "color": "#2c3e50", "marginBottom": "5px"}),
                        html.Div(f"{value:.1f}", style={"fontSize": "18px", "fontWeight": "bold", "color": "#27ae60"})
                    ], style={
                        "flex": "1",
                        "padding": "10px",
                        "textAlign": "center",
                        "border": "1px solid #bdc3c7",
                        "borderRadius": "4px",
                        "margin": "0 5px",
                        "background-color": "#ecf0f1"
                    })
                    row_metrics.append(metric_box)
            
            # Create row for this eNB
            row_div = html.Div([
                html.Div(f"eNB{enb_id}", style={
                    "minWidth": "70px",
                    "fontWeight": "bold",
                    "color": "white",
                    "background-color": "#2c3e50",
                    "padding": "10px",
                    "textAlign": "center",
                    "borderRadius": "4px 0 0 4px"
                }),
                html.Div(row_metrics, style={"display": "flex", "flex": "1"})
            ], style={
                "display": "flex",
                "marginBottom": "10px",
                "alignItems": "stretch",
                "gap": "5px"
            })
            cards.append(row_div)
    
    # System status
    load_cols = [c for c in df.columns if c.startswith("Load_ENB")]
    load_imbalance = 0.0
    overloaded = 0
    underutilized = 0
    if load_cols:
        current_loads = latest[load_cols].astype(float).values
        if len(current_loads) > 0:
            load_imbalance = float(np.max(current_loads) - np.min(current_loads))
            overloaded = int(np.sum(current_loads > 0.85))
            underutilized = int(np.sum(current_loads < 0.30))

    status_text = f"""Last Update: {datetime.now().strftime('%H:%M:%S')}
Data Points: {len(df)}
Active Errors: {len(error_injector.get_active_errors(0))}
Load Imbalance: {load_imbalance:.2f}
Overloaded Cells: {overloaded} | Underutilized Cells: {underutilized}
Model Status: Ready
"""
    
    # Load and display AI decisions
    ai_log_content = load_ai_decisions()
    
    return [figures[0], figures[1], figures[2], lb_fig, figures[3], figures[4], cards, status_text, ai_log_content]


@app.callback(
    [Output("injection-output", "children"),
     Output("error-store", "data")],
    [Input("inject-button", "n_clicks")],
    [State("error-type-dropdown", "value"),
     State("cell-id-dropdown", "value"),
     State("severity-slider", "value"),
     State("duration-slider", "value")],
    prevent_initial_call=True
)
def inject_error(n_clicks, error_type, cell_id, severity, duration):
    """Handle error injection."""
    if n_clicks == 0:
        return ["", {}]
    
    try:
        # Send error to NS3 simulator via TCP socket on port 5001
        import socket
        import time
        
        error_msg = f"type:{error_type},cell_id:{cell_id},intensity:{severity},duration:{duration}"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        try:
            logger.info(f"Connecting to NS3 on 127.0.0.1:5001 to inject: {error_msg}")
            sock.connect(("127.0.0.1", 5001))
            
            # Send error message
            sock.sendall(error_msg.encode() + b'\n')
            time.sleep(0.1)
            
            # Try to receive acknowledgment
            try:
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                logger.info(f"NS3 response: {response}")
            except socket.timeout:
                logger.warning("No response from NS3 (timeout)")
                response = "Sent (no immediate response)"
            
            sock.close()
            
            output = html.Div([
                html.P("✓ Error Injected Successfully", style={"color": "#27ae60", "fontWeight": "bold"}),
                html.P(f"Type: {error_type}", style={"margin": "5px 0"}),
                html.P(f"Cell: eNB{cell_id + 1}", style={"margin": "5px 0"}),
                html.P(f"Intensity: {severity:.1f}", style={"margin": "5px 0"}),
                html.P(f"Duration: {duration}s", style={"margin": "5px 0"}),
                html.P(f"Response: {response}", style={"margin": "5px 0", "fontSize": "11px", "color": "#666"})
            ], style={"padding": "10px", "background-color": "#d5f4e6", "borderRadius": "5px"})
            
            return [output, {"status": "success", "message": error_msg}]
        
        except (ConnectionRefusedError, OSError) as e:
            sock.close()
            logger.error(f"Cannot connect to NS3: {e}")
            output = html.Div([
                html.P("⚠ Simulator not connected", style={"color": "#f39c12", "fontWeight": "bold"}),
                html.P(f"NS3 simulator on port 5001 not available: {str(e)}", style={"margin": "5px 0", "fontSize": "11px"})
            ], style={"padding": "10px", "background-color": "#fdebd0", "borderRadius": "5px"})
            return [output, {}]
    
    except Exception as e:
        logger.error(f"Error injection failed: {e}", exc_info=True)
        output = html.Div([
            html.P("✗ Error Injection Failed", style={"color": "#e74c3c", "fontWeight": "bold"}),
            html.P(str(e), style={"margin": "5px 0", "fontSize": "11px"})
        ], style={"padding": "10px", "background-color": "#fadbd8", "borderRadius": "5px"})
        
        return [output, {}]


@app.callback(
    Output("enb-control-output", "children"),
    [Input("start-enb-button", "n_clicks"),
     Input("stop-enb-button", "n_clicks"),
     Input("ai-action-button", "n_clicks")],
    [State("enb-control-dropdown", "value")],
    prevent_initial_call=True
)
def control_enb(start_clicks, stop_clicks, ai_action_clicks, enb_id):
    """Send START/STOP/AI_ACTION commands for eNB control to NS3 control server (port 5002)."""
    trigger = dash.callback_context.triggered[0]["prop_id"].split(".")[0] if dash.callback_context.triggered else ""
    action = "START" if trigger == "start-enb-button" else "STOP"
    if trigger == "ai-action-button":
        action = "AI_ACTION"

    try:
        import socket

        def send_control_command(msg: str) -> str:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", 5002))
            sock.sendall(msg.encode() + b"\n")
            try:
                response = sock.recv(256).decode("utf-8", errors="ignore").strip()
            except socket.timeout:
                response = "Sent (no immediate response)"
            sock.close()
            return response

        if action == "AI_ACTION":
            # 1) Turn on all eNBs that may be off
            start_responses = []
            for i in range(6):
                try:
                    resp = send_control_command(f"action:START,enb_id:{i}")
                    start_responses.append(f"eNB{i+1}:{resp}")
                except Exception as e:
                    start_responses.append(f"eNB{i+1}:ERROR({str(e)})")

            # 2) Trigger immediate rebalance in simulator
            try:
                rebalance_resp = send_control_command("action:REBALANCE")
            except Exception as e:
                rebalance_resp = f"ERROR({str(e)})"

            return html.Div([
                html.P("AI Action executed: all eNBs started + rebalance triggered", style={"margin": "0", "fontWeight": "bold", "color": "#2980b9"}),
                html.P(f"Rebalance: {rebalance_resp}", style={"margin": "4px 0 0 0", "fontSize": "11px", "color": "#666"}),
                html.P("Starts: " + " | ".join(start_responses), style={"margin": "4px 0 0 0", "fontSize": "10px", "color": "#666"})
            ])

        msg = f"action:{action},enb_id:{int(enb_id)}"

        try:
            response = send_control_command(msg)

            color = "#27ae60" if action == "START" else "#e74c3c"
            return html.Div([
                html.P(f"{action} command sent to eNB{int(enb_id) + 1}", style={"margin": "0", "fontWeight": "bold", "color": color}),
                html.P(f"Response: {response}", style={"margin": "4px 0 0 0", "fontSize": "11px", "color": "#666"})
            ])

        except (ConnectionRefusedError, OSError) as e:
            return html.Div([
                html.P("Simulator control server unavailable (port 5002)", style={"margin": "0", "fontWeight": "bold", "color": "#f39c12"}),
                html.P(str(e), style={"margin": "4px 0 0 0", "fontSize": "11px", "color": "#666"})
            ])
    except Exception as e:
        logger.error(f"eNB control failed: {e}", exc_info=True)
        return html.Div([
            html.P("Failed to send eNB control command", style={"margin": "0", "fontWeight": "bold", "color": "#e74c3c"}),
            html.P(str(e), style={"margin": "4px 0 0 0", "fontSize": "11px", "color": "#666"})
        ])


if __name__ == "__main__":
    port = get_config("dashboard.port", 8050)
    debug = get_config("dashboard.debug", False)
    
    logger.info(f"Starting dashboard on port {port}...")
    app.run(debug=debug, host="127.0.0.1", port=port)
