from flask import Flask, request, jsonify, render_template
import math
import os

# Initialize Flask application with static folder configuration
# Ensure static files are properly served in both development and production
app = Flask(__name__, 
           static_url_path='/static', 
           static_folder='static',
           template_folder='templates')

# Set environment configuration
app.config['ENV'] = os.environ.get('FLASK_ENV', 'production')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# --- Constants ---
FIXED_KW = 2.0
FIXED_RU = 4 # VAST Switches RU
MAX_CABINET_RU = 42 # Adjusted Total RU for VAST gear
MAX_SYSTEM_RU = MAX_CABINET_RU - FIXED_RU # Max RU for C/D boxes = 38
MAX_CABINET_POWER = 28.50
MAX_SYSTEM_POWER = MAX_CABINET_POWER - FIXED_KW # Max Power for C/D boxes = 26.5
MAX_USABLE_POWER_TARGET_PERCENT = 90 # Safety cap

CBOX = {
    'kw': 0.5, 'ru': 1, 'ports': 2,
    'nfsWrite': 6, 'nfsRead': 29, 's3Write': 5, 's3Read': 13.2
}
DBOX = {
    'kw': 0.75, 'ru': 1, 'ports': 4,
    'nfsWrite': 12.7, 'nfsRead': 51, 's3Write': 12.7, 's3Read': 51
}

DBOX_CAPACITY_LOOKUP = [
    0, 982.67136, 2210.807808, 3447.189504, 4678.975488,
    5909.54496, 7139.303424, 8368.92672
]
DBOX_INCREMENTAL_CAPACITY = 1195.56096

# --- Helper Functions ---
def get_usable_capacity(nd):
    if nd <= 0: return 0
    if nd <= 7:
        # Ensure index is within bounds in case nd is fractional temporarily
        nd_idx = math.floor(nd)
        if nd_idx >= len(DBOX_CAPACITY_LOOKUP):
             # Fallback for safety, though shouldn't happen with integer loops
             return DBOX_CAPACITY_LOOKUP[-1] + (nd - (len(DBOX_CAPACITY_LOOKUP)-1)) * DBOX_INCREMENTAL_CAPACITY
        return DBOX_CAPACITY_LOOKUP[nd_idx]
    else:
        return DBOX_CAPACITY_LOOKUP[7] + (nd - 7) * DBOX_INCREMENTAL_CAPACITY

# --- Main Calculation Logic ---
def check_constraints(nc, nd, max_ru_allowed_target, max_power_allowed_target):
    """Check if a configuration meets all system constraints
    
    Args:
        nc: Number of C-Boxes
        nd: Number of D-Boxes
        max_ru_allowed_target: Maximum rack units allowed based on user input
        max_power_allowed_target: Maximum power allowed based on user input
        
    Returns:
        tuple: (is_feasible, current_total_ru, current_total_kw)
    """
    # System Limits
    if nc + nd > MAX_SYSTEM_RU:  # RU limit for C/D boxes
        return False, 0, 0
        
    if (nc * CBOX['ports'] + nd * DBOX['ports']) > 128:  # Network Port limit
        return False, 0, 0
        
    current_cd_kw = nc * CBOX['kw'] + nd * DBOX['kw']
    if current_cd_kw > MAX_SYSTEM_POWER:  # Absolute Power limit for C/D boxes
        return False, 0, 0

    # User Input Limits
    current_total_ru = FIXED_RU + nc + nd
    if current_total_ru > max_ru_allowed_target:  # User RU target
        return False, 0, 0
        
    current_total_kw = FIXED_KW + current_cd_kw
    if current_total_kw > max_power_allowed_target:  # User Power target
        return False, 0, 0

    # Ratio Limit (N_C >= N_D / 2)
    if nc < nd / 2.0:
        return False, 0, 0
        
    return True, current_total_ru, current_total_kw


def calculate_metrics(nc, nd, current_total_ru, current_total_kw):
    """Calculate performance metrics for a given configuration
    
    Args:
        nc: Number of C-Boxes
        nd: Number of D-Boxes
        current_total_ru: Total rack units used
        current_total_kw: Total power consumption
        
    Returns:
        dict: Metrics for the configuration
    """
    capacity = get_usable_capacity(nd)
    nfs_write = min(nc * CBOX['nfsWrite'], nd * DBOX['nfsWrite'])
    nfs_read = min(nc * CBOX['nfsRead'], nd * DBOX['nfsRead'])
    s3_write = min(nc * CBOX['s3Write'], nd * DBOX['s3Write'])
    s3_read = min(nc * CBOX['s3Read'], nd * DBOX['s3Read'])
    
    # Calculate total NFS throughput and speed-to-space ratio
    total_nfs_throughput = nfs_read + nfs_write
    speed_to_space_ratio = (total_nfs_throughput / capacity) if capacity > 0 else 0

    return {
        'capacity_tb': round(capacity, 1),
        'nfs_read_gbps': round(nfs_read, 1),
        'nfs_write_gbps': round(nfs_write, 1),
        's3_read_gbps': round(s3_read, 1),
        's3_write_gbps': round(s3_write, 1),
        'total_nfs_gbps': round(total_nfs_throughput, 1),  # Added total NFS throughput
        'speed_to_space_ratio': round(speed_to_space_ratio, 3),  # Added speed-to-space ratio
        'total_ru': current_total_ru,
        'total_kw': round(current_total_kw, 2)
    }


def update_best_configs(best, nc, nd, metrics):
    """Update the best configurations if the current one is better
    
    Args:
        best: Dictionary of current best configurations
        nc: Number of C-Boxes
        nd: Number of D-Boxes
        metrics: Performance metrics for this configuration
        
    Returns:
        dict: Updated best configurations
    """
    capacity = metrics['capacity_tb']
    nfs_read = metrics['nfs_read_gbps']
    nfs_write = metrics['nfs_write_gbps']
    s3_read = metrics['s3_read_gbps']
    s3_write = metrics['s3_write_gbps']
    speed_to_space_ratio = metrics['speed_to_space_ratio']
    
    # Check and update each optimization target
    if capacity > best['maxCapa']['value']:
        best['maxCapa'] = {'nc': nc, 'nd': nd, 'value': capacity, 'metrics': metrics}
        
    if nfs_read > best['maxNfsRead']['value']:
        best['maxNfsRead'] = {'nc': nc, 'nd': nd, 'value': nfs_read, 'metrics': metrics}
        
    if nfs_write > best['maxNfsWrite']['value']:
        best['maxNfsWrite'] = {'nc': nc, 'nd': nd, 'value': nfs_write, 'metrics': metrics}
        
    if s3_read > best['maxS3Read']['value']:
        best['maxS3Read'] = {'nc': nc, 'nd': nd, 'value': s3_read, 'metrics': metrics}
        
    if s3_write > best['maxS3Write']['value']:
        best['maxS3Write'] = {'nc': nc, 'nd': nd, 'value': s3_write, 'metrics': metrics}
    
    # Add check for maxSpeedToSpace
    if speed_to_space_ratio > best['maxSpeedToSpace']['value']:
        best['maxSpeedToSpace'] = {'nc': nc, 'nd': nd, 'value': speed_to_space_ratio, 'metrics': metrics}
        
    return best


def calculate_optimal_configs(percent_ru, percent_power):
    """Calculate optimal VAST configurations based on user constraints
    
    Args:
        percent_ru: Target rack unit utilization percentage
        percent_power: Target power consumption percentage
        
    Returns:
        dict: Optimal configurations for different optimization targets
    """
    try:
        # Convert input percentages to actual limits
        max_ru_allowed_target = math.floor(MAX_CABINET_RU * float(percent_ru) / 100)
        power_target_kw = MAX_CABINET_POWER * float(percent_power) / 100
        max_power_allowed_target = min(power_target_kw, MAX_CABINET_POWER * MAX_USABLE_POWER_TARGET_PERCENT / 100)
    except ValueError:
        # Handle cases where conversion fails
        return {"error": "Invalid percentage input."}

    # Initialize best configurations
    best = {
        'maxCapa': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}},
        'maxNfsRead': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}},
        'maxNfsWrite': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}},
        'maxS3Read': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}},
        'maxS3Write': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}},
        'maxSpeedToSpace': {'nc': 0, 'nd': 0, 'value': -1, 'metrics': {}}  # Added maxSpeedToSpace optimization goal
    }
    feasible_count = 0
    
    # Initialize list to collect all feasible configurations for visualization
    feasible_points = []

    # Loop through possible combinations
    for nc in range(2, MAX_SYSTEM_RU + 1):  # nc >= 2
        for nd in range(1, MAX_SYSTEM_RU + 1):  # nd >= 1
            # Check if configuration meets all constraints
            is_feasible, current_total_ru, current_total_kw = check_constraints(
                nc, nd, max_ru_allowed_target, max_power_allowed_target
            )
            
            if not is_feasible:
                continue
                
            # Configuration is feasible, calculate metrics
            feasible_count += 1
            metrics = calculate_metrics(nc, nd, current_total_ru, current_total_kw)
            
            # Update best configurations if this one is better
            best = update_best_configs(best, nc, nd, metrics)
            
            # Append the current feasible point's data to the feasible_points list
            feasible_points.append({
                'nc': nc,
                'nd': nd,
                'capacity_tb': metrics['capacity_tb'],
                'total_nfs_gbps': metrics['total_nfs_gbps'],
                'speed_ratio': metrics['speed_to_space_ratio']
                # Add other metrics if needed for tooltips later
            })

    # Add feasibility check - if no config is found for a goal, mark it
    for key in best:
        if best[key]['nc'] == 0:
            best[key]['metrics']['error'] = "No valid configuration found meeting all constraints."

    app.logger.info(f"Calculation complete. Found {feasible_count} feasible configurations.")
    
    # Return both the optimal configurations and the feasible points for visualization
    return {
        'optimal': best,
        'feasible_points': feasible_points
    }


# --- API Route ---
@app.route('/calculate', methods=['POST'])
def handle_calculate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    percent_ru = data.get('percentRU', 80) # Default if missing
    percent_power = data.get('percentPower', 70) # Default if missing

    app.logger.info(f"Received calculation request: RU %={percent_ru}, Power %={percent_power}")

    results = calculate_optimal_configs(percent_ru, percent_power)
    return jsonify(results)

# --- Frontend Routes ---
@app.route('/')
def index():
    """Render the main application page"""
    return render_template('index.html')

# --- Run for Development ---
if __name__ == '__main__':
    # For local development, use port 5060
    # For production deployment on DigitalOcean, use port 8080 (set in Dockerfile and .do/app.yaml)
    # Note: Never use port 5000 as it conflicts with macOS AirPlay
    # Always listen on 0.0.0.0 to be accessible from outside the container
    port = int(os.environ.get('PORT', 8080))  # Default to 8080 for DigitalOcean compatibility
    app.run(host='0.0.0.0', port=port)
