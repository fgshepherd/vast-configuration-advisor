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
FIXED_KW = 2.0  # Fixed power consumption for switches
FIXED_RU = 4    # VAST Switches RU
# Default values - these will be overridden by user input
DEFAULT_MAX_CABINET_RU = 42    # Default total RU for VAST gear
DEFAULT_MAX_CABINET_POWER = 28.50  # Default max power in kW
MAX_USABLE_POWER_TARGET_PERCENT = 90  # Safety cap

CBOX = {
    'kw': 0.5, 'ru': 1, 'ports': 2,
    'nfsWrite': 6, 'nfsRead': 29, 's3Write': 5, 's3Read': 13.2
}
DBOX = {
    'kw': 0.75, 'ru': 1, 'ports': 4,
    'nfsWrite': 12.7, 'nfsRead': 51, 's3Write': 12.7, 's3Read': 51
}

# D-Box capacity data will be loaded from CSV
DBOX_CAPACITY_LOOKUP = [0]  # Initialize with 0 for 0 boxes
DBOX_INCREMENTAL_CAPACITY = 1195.56096  # Default value, will be updated from CSV

# Load D-Box capacity data from CSV
def load_dbox_capacity_data():
    """Load D-Box capacity data from CSV file
    
    Updates the global DBOX_CAPACITY_LOOKUP and DBOX_INCREMENTAL_CAPACITY variables
    based on data from the CSV file.
    """
    import csv
    import os
    
    global DBOX_CAPACITY_LOOKUP, DBOX_INCREMENTAL_CAPACITY
    
    csv_path = os.path.join('static', 'DF-3060_capacities.csv')
    
    # Check if file exists
    if not os.path.exists(csv_path):
        app.logger.warning(f"CSV file not found: {csv_path}")
        return
    
    try:
        capacity_lookup = _parse_csv_data(csv_path)
        
        # Update global variables
        if capacity_lookup:
            DBOX_CAPACITY_LOOKUP = capacity_lookup
            app.logger.info(f"Loaded D-Box capacity data: {DBOX_CAPACITY_LOOKUP}")
            app.logger.info(f"Incremental capacity: {DBOX_INCREMENTAL_CAPACITY}")
    except Exception as e:
        app.logger.error(f"Failed to load D-Box capacity data: {e}")

def _parse_csv_data(csv_path):
    """Parse the CSV file and extract D-Box capacity data
    
    Args:
        csv_path: Path to the CSV file
        
    Returns:
        list: Capacity lookup table
    """
    import csv
    global DBOX_INCREMENTAL_CAPACITY
    
    # Initialize with 0 for 0 boxes
    capacity_lookup = [0]
    
    with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header row
        
        for row in reader:
            if len(row) < 4:  # Skip rows without enough columns
                continue
                
            try:
                num_dboxes = int(row[0])
                total_capacity = float(row[3])
                
                # Add to lookup table if it's the next sequential number
                if num_dboxes == len(capacity_lookup):
                    capacity_lookup.append(total_capacity)
                    
                    # Update incremental capacity based on the last two entries
                    # Use D-Boxes 8 and 9 to calculate the incremental capacity
                    if num_dboxes >= 8 and num_dboxes <= 9:
                        DBOX_INCREMENTAL_CAPACITY = total_capacity - capacity_lookup[num_dboxes-1]
            except (ValueError, IndexError) as e:
                app.logger.warning(f"Error parsing CSV row: {row}. Error: {e}")
                
    return capacity_lookup

# Load capacity data when app starts
load_dbox_capacity_data()

# --- Helper Functions ---
def get_usable_capacity(nd):
    """Calculate usable capacity for a given number of D-Boxes
    
    Args:
        nd: Number of D-Boxes
        
    Returns:
        float: Usable capacity in TB
    """
    if nd <= 0: return 0
    
    # Ensure index is within bounds
    nd_idx = math.floor(nd)
    
    if nd_idx < len(DBOX_CAPACITY_LOOKUP):
        # Use exact value from lookup table
        return DBOX_CAPACITY_LOOKUP[nd_idx]
    else:
        # Use incremental capacity for larger numbers
        highest_known_index = len(DBOX_CAPACITY_LOOKUP) - 1
        highest_known_value = DBOX_CAPACITY_LOOKUP[highest_known_index]
        return highest_known_value + (nd - highest_known_index) * DBOX_INCREMENTAL_CAPACITY

# --- Main Calculation Logic ---
def check_constraints(nc, nd, max_ru_allowed_target, max_power_allowed_target, max_cabinet_ru, max_system_power):
    """Check if a configuration meets all system constraints
    
    Args:
        nc: Number of C-Boxes
        nd: Number of D-Boxes
        max_ru_allowed_target: Maximum rack units allowed based on user input
        max_power_allowed_target: Maximum power allowed based on user input
        max_cabinet_ru: Total rack units available
        max_system_power: Maximum system power available for C/D boxes
        
    Returns:
        tuple: (is_feasible, current_total_ru, current_total_kw)
    """
    # Calculate max system RU (total minus fixed switches)
    max_system_ru = max_cabinet_ru - FIXED_RU
    
    # System Limits
    if nc + nd > max_system_ru:  # RU limit for C/D boxes
        return False, 0, 0
        
    if (nc * CBOX['ports'] + nd * DBOX['ports']) > 128:  # Network Port limit
        return False, 0, 0
        
    current_cd_kw = nc * CBOX['kw'] + nd * DBOX['kw']
    if current_cd_kw > max_system_power:  # Absolute Power limit for C/D boxes
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


def calculate_metrics(nc, nd, current_total_ru, current_total_kw, max_cabinet_ru, max_cabinet_power):
    """Calculate performance metrics for a given configuration
    
    Args:
        nc: Number of C-Boxes
        nd: Number of D-Boxes
        current_total_ru: Total rack units used
        current_total_kw: Total power consumption
        max_cabinet_ru: Total rack units available
        max_cabinet_power: Maximum cabinet power in kW
        
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
    total_s3_throughput = s3_read + s3_write  # Calculate total S3 throughput
    speed_to_space_ratio = (total_nfs_throughput / capacity) if capacity > 0 else 0
    
    # Calculate percentage utilization metrics
    ru_percent = (current_total_ru / max_cabinet_ru * 100) if max_cabinet_ru > 0 else 0
    power_percent = (current_total_kw / max_cabinet_power * 100) if max_cabinet_power > 0 else 0

    return {
        'capacity_tb': round(capacity, 1),
        'nfs_read_gbps': round(nfs_read, 1),
        'nfs_write_gbps': round(nfs_write, 1),
        's3_read_gbps': round(s3_read, 1),
        's3_write_gbps': round(s3_write, 1),
        'total_nfs_gbps': round(total_nfs_throughput, 1),  # Added total NFS throughput
        'total_s3_gbps': round(total_s3_throughput, 1),  # Added total S3 throughput
        'speed_to_space_ratio': round(speed_to_space_ratio, 3),  # Added speed-to-space ratio
        'total_ru': current_total_ru,
        'max_ru': max_cabinet_ru,  # Added max RU for percentage calculation
        'total_kw': round(current_total_kw, 2),
        'max_kw': max_cabinet_power,  # Added max power for percentage calculation
        'ru_percent': round(ru_percent, 1),  # Added rack unit utilization percentage
        'power_percent': round(power_percent, 1)  # Added power utilization percentage
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


def calculate_optimal_configs(rack_units, power_option, percent_ru, percent_power):
    """Calculate optimal VAST configurations based on user constraints
    
    Args:
        rack_units: Total rack units available
        power_option: Power capacity option in kW
        percent_ru: Target rack unit utilization percentage
        percent_power: Target power consumption percentage
        
    Returns:
        dict: Optimal configurations for different optimization targets
    """
    try:
        # Use user-provided values for rack units and power
        max_cabinet_ru = float(rack_units)
        max_cabinet_power = float(power_option)
        
        # Calculate max system power (total minus fixed switches)
        max_system_power = max_cabinet_power - FIXED_KW
        
        # Convert input percentages to actual limits
        max_ru_allowed_target = math.floor(max_cabinet_ru * float(percent_ru) / 100)
        power_target_kw = max_cabinet_power * float(percent_power) / 100
        max_power_allowed_target = min(power_target_kw, max_cabinet_power * MAX_USABLE_POWER_TARGET_PERCENT / 100)
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
    # Use max_cabinet_ru instead of the constant
    max_system_ru = max_cabinet_ru - FIXED_RU
    for nc in range(2, int(max_system_ru) + 1):  # nc >= 2
        for nd in range(1, int(max_system_ru) + 1):  # nd >= 1
            # Check if configuration meets all constraints
            is_feasible, current_total_ru, current_total_kw = check_constraints(
                nc, nd, max_ru_allowed_target, max_power_allowed_target, max_cabinet_ru, max_system_power
            )
            
            if not is_feasible:
                continue
                
            # Configuration is feasible, calculate metrics
            feasible_count += 1
            metrics = calculate_metrics(nc, nd, current_total_ru, current_total_kw, max_cabinet_ru, max_cabinet_power)
            
            # Update best configurations if this one is better
            best = update_best_configs(best, nc, nd, metrics)
            
            # Append the current feasible point's data to the feasible_points list with ALL metrics
            # This ensures the chart has all the data it needs for visualization
            feasible_points.append({
                # Configuration details
                'nc': nc,
                'nd': nd,
                
                # Performance metrics
                'capacity_tb': metrics['capacity_tb'],
                'nfs_read_gbps': metrics['nfs_read_gbps'],
                'nfs_write_gbps': metrics['nfs_write_gbps'],
                's3_read_gbps': metrics['s3_read_gbps'],
                's3_write_gbps': metrics['s3_write_gbps'],
                'total_nfs_gbps': metrics['total_nfs_gbps'],
                'total_s3_gbps': metrics['total_s3_gbps'],
                'speed_to_space_ratio': metrics['speed_to_space_ratio'],
                
                # Resource utilization metrics
                'total_ru': metrics['total_ru'],
                'max_ru': metrics['max_ru'],
                'total_kw': metrics['total_kw'],
                'max_kw': metrics['max_kw'],
                'ru_percent': metrics['ru_percent'],
                'power_percent': metrics['power_percent']
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

    # Get parameters from request with defaults
    rack_units = data.get('rackUnits', DEFAULT_MAX_CABINET_RU)  # Default to 42U if missing
    power_option = data.get('powerOption', DEFAULT_MAX_CABINET_POWER)  # Default to 28.50 kW if missing
    percent_ru = data.get('percentRU', 80)  # Default if missing
    percent_power = data.get('percentPower', 70)  # Default if missing

    app.logger.info(f"Received calculation request: Rack Units={rack_units}, Power Option={power_option} kW, RU %={percent_ru}, Power %={percent_power}")

    results = calculate_optimal_configs(rack_units, power_option, percent_ru, percent_power)
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
    port = int(os.environ.get('PORT', 5094))  # Default to 5094 for local development, 8080 for DigitalOcean
    app.run(host='0.0.0.0', port=port)
