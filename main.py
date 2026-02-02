import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime
from typing import List, Tuple, Optional
import sys
import traceback
from threading import Thread
import queue

# ================================================
# DATABASE CONNECTION & SETUP - OPTIMIZED
# ================================================

class Database:
    """Singleton database connection with improved performance"""
    _connection = None
    _connection_pool = []
    
    @classmethod
    def get_connection(cls):
        """Get database connection with connection pooling"""
        if cls._connection is None or not cls._connection.is_connected():
            try:
                cls._connection = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",  # Your MySQL password here
                    database="me_database",
                    charset='utf8mb4',
                    collation='utf8mb4_unicode_ci',
                    autocommit=False,
                    pool_name="mypool",
                    pool_size=5,
                    pool_reset_session=True
                )
            except mysql.connector.Error as err:
                cls._connection = None
                cls.show_connection_error(err)
        return cls._connection
    
    @classmethod
    def show_connection_error(cls, err):
        """Show database connection error"""
        error_msg = (
            f"Failed to connect to database:\n\n{err}\n\n"
            f"Please ensure:\n"
            f"1. MySQL is running\n"
            f"2. Database 'me_database' exists\n"
            f"3. User 'root' has correct permissions"
        )
        messagebox.showerror("Database Error", error_msg)
    
    @classmethod
    def setup_database(cls):
        """Setup database tables if not exists - OPTIMIZED"""
        try:
            # First, ensure the database exists
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="",
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS me_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            print(f"Database creation warning: {err}")
            return
        
        # Now create tables in me_database
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS spareparts (
                id INT PRIMARY KEY AUTO_INCREMENT,
                product_number VARCHAR(50),
                spare_name VARCHAR(200) NOT NULL,
                material_type VARCHAR(100),
                stock INT DEFAULT 0,
                min_stock INT DEFAULT 5,
                rack_location VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_spare_name (spare_name),
                INDEX idx_stock (stock)
            ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS physical_quantity (
                id INT PRIMARY KEY AUTO_INCREMENT,
                spare_id INT NOT NULL,
                product_number VARCHAR(50),
                spare_name VARCHAR(200) NOT NULL,
                system_qty INT DEFAULT 0,
                physical_qty INT DEFAULT 0,
                variance INT DEFAULT 0,
                checked_by VARCHAR(100),
                check_date DATETIME,
                notes TEXT,
                status ENUM('Pending', 'Verified', 'Adjusted') DEFAULT 'Pending',
                adjustment_date DATETIME,
                FOREIGN KEY (spare_id) REFERENCES spareparts(id) ON DELETE CASCADE,
                INDEX idx_spare_id (spare_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_usage (
                id INT PRIMARY KEY AUTO_INCREMENT,
                date_time DATETIME NOT NULL,
                item_name VARCHAR(200) NOT NULL,
                item_number VARCHAR(50),
                qty_stock INT DEFAULT 0,
                qty_used INT DEFAULT 0,
                machine_name VARCHAR(100),
                notes TEXT,
                issued_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_date_time (date_time)
            ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_adjustments (
                id INT PRIMARY KEY AUTO_INCREMENT,
                spare_id INT NOT NULL,
                spare_name VARCHAR(200) NOT NULL,
                adjustment_type ENUM('Correction', 'Damage', 'Loss', 'Found', 'Transfer'),
                old_qty INT DEFAULT 0,
                new_qty INT DEFAULT 0,
                difference INT DEFAULT 0,
                reason TEXT,
                adjusted_by VARCHAR(100),
                adjustment_date DATETIME,
                notes TEXT,
                FOREIGN KEY (spare_id) REFERENCES spareparts(id) ON DELETE CASCADE,
                INDEX idx_adjustment_date (adjustment_date)
            ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INT PRIMARY KEY AUTO_INCREMENT,
                spare_id INT NOT NULL,
                spare_name VARCHAR(200) NOT NULL,
                movement_type ENUM('In', 'Out', 'Adjust', 'Transfer'),
                quantity INT NOT NULL,
                from_location VARCHAR(100),
                to_location VARCHAR(100),
                reference_no VARCHAR(100),
                notes TEXT,
                created_by VARCHAR(100),
                created_at DATETIME,
                FOREIGN KEY (spare_id) REFERENCES spareparts(id) ON DELETE CASCADE,
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        ]
        
        conn = cls.get_connection()
        if conn:
            cursor = conn.cursor()
            for sql in tables_sql:
                try:
                    cursor.execute(sql)
                except mysql.connector.Error as err:
                    if "already exists" not in str(err):
                        print(f"Table creation warning: {err}")
            conn.commit()
            cursor.close()
    
    @classmethod
    def execute_query(cls, query: str, params: tuple = None, fetch: bool = False, commit: bool = True):
        """Execute SQL query with proper error handling"""
        result = None
        conn = cls.get_connection()
        
        if not conn:
            return result
            
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
            elif commit:
                conn.commit()
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            if conn:
                conn.rollback()
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            
        return result
    
    @classmethod
    def execute_many(cls, query: str, params_list: list):
        """Execute multiple SQL queries"""
        conn = cls.get_connection()
        if not conn:
            return
        
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
        except Exception as e:
            print(f"Execute many error: {e}")
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
    
    @classmethod
    def close_connection(cls):
        """Close database connection"""
        if cls._connection and cls._connection.is_connected():
            cls._connection.close()
            cls._connection = None


# ================================================
# UTILITY FUNCTIONS
# ================================================

def center_window_on_screen(window, width=None, height=None):
    """
    Universal function to center any window on screen
    Works for both Tk and Toplevel windows
    """
    window.update_idletasks()
    
    # Get window dimensions
    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()
    
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate position
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    # Ensure window is not off-screen
    x = max(0, x)
    y = max(0, y)
    
    # Set geometry
    window.geometry(f'{width}x{height}+{x}+{y}')
    window.update_idletasks()

def format_variance(value: int) -> str:
    """Format variance value with +/- sign"""
    if value > 0:
        return f"+{value}"
    elif value < 0:
        return str(value)
    return "0"

def get_status_info(sys_qty: int, phy_qty: int, variance: int, min_stock: int, pqt_status: str) -> Tuple[str, tuple]:
    """Get status icon and tags based on quantities"""
    if sys_qty == 0:
        return "🔴", ('missing',)
    elif variance != 0:
        if pqt_status == 'Verified':
            return "⚠️", ('variance',)
        else:
            return "❓", ('variance', 'no_check')
    elif sys_qty <= min_stock:
        return "🟡", ('low_stock',)
    elif phy_qty == sys_qty or pqt_status == 'Verified':
        return "✅", ('match',)
    else:
        return "📊", ('no_check',)

def validate_integer(value: str, field_name: str = "Quantity") -> Tuple[bool, int, str]:
    """Validate integer input"""
    if not value.strip():
        return False, 0, f"{field_name} cannot be empty!"
    
    try:
        int_value = int(value)
        if int_value <= 0:
            return False, 0, f"{field_name} must be positive!"
        return True, int_value, ""
    except ValueError:
        return False, 0, f"Invalid {field_name.lower()} format!"


# ================================================
# LOADING SCREEN - UNTUK STARTUP YANG LEBIH SMOOTH
# ================================================

class LoadingScreen:
    """Loading screen untuk startup aplikasi"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Loading...")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        self.root.configure(bg='#2c3e50')
        self.root.overrideredirect(True)
        
        # Create UI first
        self.create_ui()
        
        # Center window after creation
        self.center_window()
        
    def center_window(self):
        """Center window on screen"""
        center_window_on_screen(self.root, 400, 250)
    
    def create_ui(self):
        """Create loading UI"""
        # Icon
        tk.Label(self.root,
                text="📊",
                font=('Segoe UI', 48),
                bg='#2c3e50',
                fg='white').pack(pady=(30, 10))
        
        # Title
        tk.Label(self.root,
                text="Sparepart Management",
                font=('Segoe UI', 16, 'bold'),
                bg='#2c3e50',
                fg='white').pack()
        
        tk.Label(self.root,
                text="with PQT System",
                font=('Segoe UI', 12),
                bg='#2c3e50',
                fg='#bdc3c7').pack()
        
        # Status label
        self.status_label = tk.Label(self.root,
                                     text="Initializing...",
                                     font=('Segoe UI', 10),
                                     bg='#2c3e50',
                                     fg='#ecf0f1')
        self.status_label.pack(pady=(20, 10))
        
        # Progress bar
        self.progress = ttk.Progressbar(self.root,
                                       length=300,
                                       mode='indeterminate')
        self.progress.pack(pady=(0, 20))
        self.progress.start(10)
    
    def update_status(self, text):
        """Update status text"""
        self.status_label.config(text=text)
        self.root.update()
    
    def close(self):
        """Close loading screen"""
        self.progress.stop()
        self.root.destroy()


# ================================================
# MAIN APPLICATION - OPTIMIZED
# ================================================

class SparepartApp:
    """Main application with Physical Quantity Tracking - OPTIMIZED"""
    
    def __init__(self, loading_screen=None):
        self.loading_screen = loading_screen
        self.root = tk.Tk()
        self.root.title("Sparepart Management - PQt System")
        self.root.geometry("1600x900")
        self.root.configure(bg='#f5f6fa')
        
        # Withdraw window during initialization
        self.root.withdraw()
        
        # Modern color scheme
        self.colors = {
            'primary': '#2c3e50',
            'primary_light': '#34495e',
            'secondary': '#3498db',
            'accent': '#e74c3c',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'danger': '#c0392b',
            'light': '#ecf0f1',
            'dark': '#2c3e50',
            'gray': '#bdc3c7',
            'card': '#ffffff',
        }
        
        # Data cache
        self.parts_data_cache = []
        self.items_cache = []
        
        # Initialize in stages
        self.initialize()
    
    def initialize(self):
        """Initialize application in stages"""
        try:
            if self.loading_screen:
                self.loading_screen.update_status("Setting up styles...")
            self.setup_styles()
            
            if self.loading_screen:
                self.loading_screen.update_status("Creating layout...")
            self.create_layout()
            
            if self.loading_screen:
                self.loading_screen.update_status("Loading data...")
            
            # Load data in background thread
            self.data_queue = queue.Queue()
            self.load_thread = Thread(target=self.load_data_background, daemon=True)
            self.load_thread.start()
            
            # Check data loading progress
            self.check_data_loading()
            
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize: {str(e)}")
            self.root.destroy()
    
    def load_data_background(self):
        """Load data in background thread"""
        try:
            # Load items for combo
            query = """
                SELECT DISTINCT s.spare_name 
                FROM spareparts s
                WHERE s.stock > 0 
                ORDER BY s.spare_name
            """
            results = Database.execute_query(query, fetch=True)
            
            if results:
                items = [row[0] for row in results]
                self.data_queue.put(('items', items))
            
            # Load parts list
            query = """
                SELECT 
                    s.id,
                    s.spare_name,
                    s.material_type,
                    s.stock as system_qty,
                    COALESCE(p.physical_qty, s.stock) as physical_qty,
                    COALESCE(p.variance, 0) as variance,
                    s.rack_location,
                    COALESCE(DATE_FORMAT(p.check_date, '%Y-%m-%d'), 'Never') as last_check,
                    s.min_stock,
                    COALESCE(p.status, 'Pending') as pqt_status
                FROM spareparts s
                LEFT JOIN physical_quantity p ON s.id = p.spare_id
                ORDER BY 
                    CASE 
                        WHEN s.stock = 0 THEN 1
                        WHEN COALESCE(p.variance, 0) != 0 THEN 2
                        WHEN s.stock <= s.min_stock AND s.stock > 0 THEN 3
                        ELSE 4
                    END,
                    s.spare_name
            """
            results = Database.execute_query(query, fetch=True)
            
            if results:
                self.data_queue.put(('parts', results))
            
            # Signal completion
            self.data_queue.put(('complete', None))
            
        except Exception as e:
            self.data_queue.put(('error', str(e)))
    
    def check_data_loading(self):
        """Check if data loading is complete"""
        try:
            while True:
                msg_type, data = self.data_queue.get_nowait()
                
                if msg_type == 'items':
                    self.items_cache = data
                    self.item_combo['values'] = data
                    if data:
                        self.item_combo.set(data[0])
                        self.on_item_selected()
                
                elif msg_type == 'parts':
                    self.parts_data_cache = data
                    self.populate_tree(data)
                
                elif msg_type == 'complete':
                    # Data loading complete
                    if self.loading_screen:
                        self.loading_screen.update_status("Ready!")
                        self.root.after(500, self.show_main_window)
                    else:
                        self.show_main_window()
                    return
                
                elif msg_type == 'error':
                    messagebox.showerror("Data Loading Error", f"Failed to load data: {data}")
                    self.show_main_window()
                    return
        
        except queue.Empty:
            # Keep checking
            self.root.after(100, self.check_data_loading)
    
    def show_main_window(self):
        """Show main window after loading"""
        if self.loading_screen:
            self.loading_screen.close()
        
        # Ensure window is centered before showing
        self.root.update_idletasks()
        self.center_window()
        self.root.deiconify()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def populate_tree(self, data):
        """Populate treeview with data"""
        self.parts_tree.delete(*self.parts_tree.get_children())
        
        for row in data:
            spare_id, name, material, sys_qty, phy_qty, variance, rack, last_check, min_stock, pqt_status = row
            
            status_icon, tags = get_status_info(sys_qty, phy_qty, variance, min_stock, pqt_status)
            
            self.parts_tree.insert('', 'end',
                values=(status_icon, name, material, sys_qty, phy_qty, 
                       format_variance(variance), rack or "-", last_check),
                tags=tags)
    
    def setup_styles(self):
        """Configure custom styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('TLabel', background=self.colors['light'])
        style.configure('TFrame', background=self.colors['light'])
        
        # Configure treeview
        style.configure('Treeview',
                       background='white',
                       foreground='black',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='flat')
        style.map('Treeview', background=[('selected', '#3498db')])
        
        style.configure('Treeview.Heading',
                       background=self.colors['primary_light'],
                       foreground='white',
                       relief='flat',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Treeview.Heading',
                 background=[('active', self.colors['primary'])])
    
    def create_layout(self):
        """Create main application layout"""
        # Header
        self.create_header()
        
        # Main content
        main_container = tk.PanedWindow(self.root, 
                                       orient='horizontal', 
                                       bg=self.colors['light'], 
                                       sashwidth=10,
                                       sashrelief='raised',
                                       sashpad=5)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left: Input Form
        form_container = self.create_input_form()
        main_container.add(form_container, minsize=800, stretch='always')
        
        # Right: Parts List
        list_container = self.create_parts_list()
        main_container.add(list_container, minsize=700, stretch='always')
    
    def create_header(self):
        """Create application header"""
        header_frame = tk.Frame(self.root, 
                               bg=self.colors['primary'], 
                               height=80)
        header_frame.pack(fill='x', side='top')
        header_frame.pack_propagate(False)
        
        # Title
        title_frame = tk.Frame(header_frame, bg=self.colors['primary'])
        title_frame.pack(side='left', padx=30, pady=20)
        
        tk.Label(title_frame,
                text="📊",
                font=('Segoe UI', 24),
                bg=self.colors['primary'],
                fg='white').pack(side='left', padx=(0, 15))
        
        title_label = tk.Label(title_frame,
                              text="SPAREPART MANAGEMENT WITH PQT",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['primary'],
                              fg='white')
        title_label.pack(side='left')
        
        # Buttons
        button_frame = tk.Frame(header_frame, bg=self.colors['primary'])
        button_frame.pack(side='right', padx=20)
        
        buttons = [
            ("🔐 Admin", self.open_admin_login, self.colors['warning']),
            ("📋 PQt Check", self.open_pqt_check, self.colors['success']),
            ("📊 Reports", self.open_reports, self.colors['secondary']),
        ]
        
        for text, command, color in buttons:
            btn = tk.Button(button_frame,
                           text=text,
                           command=command,
                           bg=color,
                           fg='white',
                           font=('Segoe UI', 10, 'bold'),
                           relief='flat',
                           cursor='hand2',
                           padx=15,
                           pady=5,
                           activebackground=color,
                           activeforeground='white')
            btn.pack(side='left', padx=5)
    
    def create_input_form(self):
        """Create the input form"""
        form_container = tk.Frame(self.root, 
                                 bg=self.colors['card'],
                                 relief='flat',
                                 bd=1)
        
        # Form title
        form_header = tk.Frame(form_container, 
                              bg=self.colors['secondary'], 
                              height=50)
        form_header.pack(fill='x', side='top')
        form_header.pack_propagate(False)
        
        tk.Label(form_header,
                text="📤 PENGAMBILAN SPAREPART (ME)",
                font=('Segoe UI', 14, 'bold'),
                bg=self.colors['secondary'],
                fg='white').pack(pady=13)
        
        # Form content
        form_content = tk.Frame(form_container, bg=self.colors['card'])
        form_content.pack(fill='both', expand=True, padx=30, pady=30)
        
        # Create form fields
        self.create_form_fields(form_content)
        
        # Update time
        self.update_datetime()
        
        return form_container
    
    def create_form_fields(self, parent):
        """Create form input fields"""
        row = 0
        
        # Date & Time
        tk.Label(parent,
                text="📅 Date & Time:",
                font=('Segoe UI', 11, 'bold'),
                bg=self.colors['card'],
                fg=self.colors['primary']).grid(row=row, column=0, sticky='w', pady=(0, 10))
        
        self.datetime_label = tk.Label(parent,
                                      text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                      font=('Segoe UI', 11),
                                      bg=self.colors['card'],
                                      fg=self.colors['dark'])
        self.datetime_label.grid(row=row, column=1, sticky='w', pady=(0, 10))
        row += 1
        
        ttk.Separator(parent, orient='horizontal').grid(row=row, column=0, 
                                                       columnspan=2, sticky='ew', 
                                                       pady=20)
        row += 1
        
        # Item Selection
        tk.Label(parent,
                text="🔧 Select Item:",
                font=('Segoe UI', 11),
                bg=self.colors['card']).grid(row=row, column=0, sticky='w', pady=(0, 10))
        
        self.item_combo = ttk.Combobox(parent,
                                      font=('Segoe UI', 11),
                                      width=40,
                                      state='readonly')
        self.item_combo.grid(row=row, column=1, sticky='w', pady=(0, 10))
        self.item_combo.bind('<<ComboboxSelected>>', self.on_item_selected)
        row += 1
        
        # Item Details
        details_frame = tk.LabelFrame(parent, 
                                     text="Item Details",
                                     font=('Segoe UI', 10, 'bold'),
                                     bg=self.colors['card'],
                                     fg=self.colors['primary'],
                                     relief='solid',
                                     bd=1)
        details_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=20)
        details_frame.grid_columnconfigure(1, weight=1)
        details_frame.grid_columnconfigure(3, weight=1)
        
        # Configure padding for details frame content
        details_frame_inner = tk.Frame(details_frame, bg=self.colors['card'], padx=15, pady=10)
        details_frame_inner.pack(fill='both', expand=True)
        
        self.create_item_details(details_frame_inner)
        row += 1
        
        # Quantity to take
        tk.Label(parent,
                text="➖ Quantity to Take:",
                font=('Segoe UI', 11),
                bg=self.colors['card']).grid(row=row, column=0, sticky='w', pady=(20, 5))
        
        self.qty_entry = tk.Entry(parent,
                                 font=('Segoe UI', 12),
                                 width=15,
                                 relief='solid',
                                 bd=2,
                                 bg='white')
        self.qty_entry.grid(row=row, column=1, sticky='w', pady=(20, 5))
        row += 1
        
        # Machine Name
        tk.Label(parent,
                text="🏭 Machine Name:",
                font=('Segoe UI', 11),
                bg=self.colors['card']).grid(row=row, column=0, sticky='w', pady=(15, 5))
        
        self.machine_entry = tk.Entry(parent,
                                     font=('Segoe UI', 12),
                                     width=30,
                                     relief='solid',
                                     bd=2,
                                     bg='white')
        self.machine_entry.grid(row=row, column=1, sticky='w', pady=(15, 5))
        row += 1
        
        # Request ID (Optional)
        tk.Label(parent,
                text="📝 Request ID (Optional):",
                font=('Segoe UI', 11),
                bg=self.colors['card']).grid(row=row, column=0, sticky='w', pady=(15, 5))
        
        self.req_entry = tk.Entry(parent,
                                 font=('Segoe UI', 12),
                                 width=30,
                                 relief='solid',
                                 bd=2,
                                 bg='white')
        self.req_entry.grid(row=row, column=1, sticky='w', pady=(15, 5))
        row += 1
        
        # Notes
        tk.Label(parent,
                text="📋 Notes:",
                font=('Segoe UI', 11),
                bg=self.colors['card']).grid(row=row, column=0, sticky='w', pady=(15, 5))
        
        self.notes_text = tk.Text(parent,
                                 font=('Segoe UI', 11),
                                 height=4,
                                 width=40,
                                 relief='solid',
                                 bd=2,
                                 bg='white')
        self.notes_text.grid(row=row, column=1, sticky='w', pady=(15, 5))
        row += 1
        
        # Button Frame
        button_frame = tk.Frame(parent, bg=self.colors['card'])
        button_frame.grid(row=row, column=0, columnspan=2, pady=30)
        
        # Submit Button
        submit_btn = tk.Button(button_frame,
                              text="✅ SUBMIT PENGAMBILAN",
                              command=self.submit_transaction,
                              bg=self.colors['accent'],
                              fg='white',
                              font=('Segoe UI', 12, 'bold'),
                              relief='flat',
                              cursor='hand2',
                              height=2,
                              width=20,
                              activebackground='#c0392b',
                              activeforeground='white')
        submit_btn.pack(side='left', padx=10)
        
        # Clear Button
        clear_btn = tk.Button(button_frame,
                             text="🗑️ CLEAR FORM",
                             command=self.clear_form,
                             bg=self.colors['gray'],
                             fg='white',
                             font=('Segoe UI', 11, 'bold'),
                             relief='flat',
                             cursor='hand2',
                             height=2,
                             width=15,
                             activebackground='#95a5a6',
                             activeforeground='white')
        clear_btn.pack(side='left', padx=10)
    
    def create_item_details(self, parent):
        """Create item details display"""
        details = [
            ("Item No:", 'item_no_label', '-', self.colors['primary']),
            ("Material:", 'material_label', '-', self.colors['primary']),
            ("System Stock:", 'system_qty_label', '0', self.colors['primary']),
            ("Physical Qty:", 'physical_qty_label', '0', self.colors['warning']),
            ("Variance:", 'variance_label', '0', '#6c757d'),
            ("Rack Location:", 'rack_label', 'Not Assigned', self.colors['success']),
        ]
        
        self.detail_labels = {}
        
        for i, (label_text, name, default_value, color) in enumerate(details):
            row = i
            col = 0
            
            # Label
            tk.Label(parent,
                    text=label_text,
                    font=('Segoe UI', 10, 'bold'),
                    bg=self.colors['card'],
                    fg=self.colors['dark']).grid(row=row, column=col, sticky='w', padx=(0, 10), pady=5)
            
            # Value
            value_label = tk.Label(parent,
                                  text=default_value,
                                  font=('Segoe UI', 10),
                                  bg=self.colors['card'],
                                  fg=color,
                                  anchor='w',
                                  width=20)
            value_label.grid(row=row, column=col+1, sticky='w', pady=5)
            
            self.detail_labels[name] = value_label
    
    def create_parts_list(self):
        """Create the parts list with PQt status"""
        list_container = tk.Frame(self.root, 
                                 bg=self.colors['card'],
                                 relief='flat',
                                 bd=1)
        
        # List header
        list_header = tk.Frame(list_container, 
                              bg=self.colors['primary_light'], 
                              height=50)
        list_header.pack(fill='x', side='top')
        list_header.pack_propagate(False)
        
        tk.Label(list_header,
                text="📋 INVENTORY STATUS WITH PQT",
                font=('Segoe UI', 14, 'bold'),
                bg=self.colors['primary_light'],
                fg='white').pack(pady=13)
        
        # Filter controls
        self.create_filter_controls(list_container)
        
        # Treeview
        self.create_treeview(list_container)
        
        return list_container
    
    def create_filter_controls(self, parent):
        """Create filter controls for parts list"""
        filter_frame = tk.Frame(parent, bg=self.colors['card'])
        filter_frame.pack(fill='x', padx=15, pady=15)
        
        # Filter label
        tk.Label(filter_frame,
                text="Filter by Status:",
                font=('Segoe UI', 10, 'bold'),
                bg=self.colors['card']).pack(side='left', padx=(0, 10))
        
        # Status filter
        self.filter_var = tk.StringVar(value="all")
        statuses = [
            ("All", "all"),
            ("✅ In Stock", "in_stock"),
            ("🟡 Low Stock", "low_stock"),
            ("🔴 Out of Stock", "out_of_stock"),
            ("📊 Needs PQt", "needs_pqt"),
            ("❌ Variance", "variance")
        ]
        
        for text, value in statuses:
            btn = tk.Radiobutton(filter_frame,
                                text=text,
                                variable=self.filter_var,
                                value=value,
                                command=self.apply_filter,
                                bg=self.colors['card'],
                                font=('Segoe UI', 9),
                                cursor='hand2',
                                selectcolor=self.colors['light'])
            btn.pack(side='left', padx=5)
        
        # Search frame
        search_frame = tk.Frame(parent, bg=self.colors['card'])
        search_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        # Search label
        tk.Label(search_frame,
                text="🔍 Search:",
                font=('Segoe UI', 10, 'bold'),
                bg=self.colors['card']).pack(side='left', padx=(0, 10))
        
        # Search entry
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.apply_filter())
        
        search_entry = tk.Entry(search_frame,
                               textvariable=self.search_var,
                               font=('Segoe UI', 11),
                               width=25,
                               relief='solid',
                               bd=2,
                               bg='white')
        search_entry.pack(side='left', padx=(0, 10))
        
        # Buttons
        btn_frame = tk.Frame(search_frame, bg=self.colors['card'])
        btn_frame.pack(side='right', fill='x', expand=True)
        
        refresh_btn = tk.Button(btn_frame,
                               text="🔄 Refresh",
                               command=self.load_parts_list,
                               bg=self.colors['primary'],
                               fg='white',
                               font=('Segoe UI', 9, 'bold'),
                               relief='flat',
                               cursor='hand2',
                               padx=10,
                               pady=5,
                               activebackground=self.colors['primary_light'],
                               activeforeground='white')
        refresh_btn.pack(side='right', padx=5)
        
        export_btn = tk.Button(btn_frame,
                              text="📥 Export",
                              command=self.export_data,
                              bg=self.colors['success'],
                              fg='white',
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat',
                              cursor='hand2',
                              padx=10,
                              pady=5,
                              activebackground='#27ae60',
                              activeforeground='white')
        export_btn.pack(side='right', padx=5)
    
    def create_treeview(self, parent):
        """Create treeview for parts list"""
        tree_frame = tk.Frame(parent, bg=self.colors['card'])
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Create Treeview
        columns = ('status', 'name', 'material', 'sys_qty', 'phy_qty', 'variance', 'rack', 'last_check')
        self.parts_tree = ttk.Treeview(tree_frame,
                                      columns=columns,
                                      show='headings',
                                      height=25,
                                      selectmode='browse')
        
        # Configure columns
        column_config = [
            ('status', 'Status', 80, 'center'),
            ('name', 'Spare Name', 250, 'w'),
            ('material', 'Material', 120, 'w'),
            ('sys_qty', 'System Qty', 90, 'center'),
            ('phy_qty', 'Physical Qty', 90, 'center'),
            ('variance', 'Variance', 90, 'center'),
            ('rack', 'Rack', 70, 'center'),
            ('last_check', 'Last Check', 120, 'center'),
        ]
        
        for col, heading, width, anchor in column_config:
            self.parts_tree.heading(col, text=heading)
            self.parts_tree.column(col, width=width, anchor=anchor, minwidth=50)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, 
                           orient='vertical', 
                           command=self.parts_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, 
                           orient='horizontal', 
                           command=self.parts_tree.xview)
        self.parts_tree.configure(yscrollcommand=vsb.set, 
                                 xscrollcommand=hsb.set)
        
        # Layout
        self.parts_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        # Configure grid weights
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Configure tags with colors
        tag_colors = {
            'match': '#d4edda',
            'variance': '#fff3cd',
            'missing': '#f8d7da',
            'low_stock': '#ffe6cc',
            'no_check': '#f0f0f0',
        }
        
        for tag, color in tag_colors.items():
            self.parts_tree.tag_configure(tag, background=color)
        
        # Bind selection
        self.parts_tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.parts_tree.bind('<Double-1>', self.on_tree_double_click)
    
    def update_datetime(self):
        """Update date time label"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.datetime_label.config(text=current_time)
            self.root.after(1000, self.update_datetime)
        except:
            pass
    
    def load_parts_list(self):
        """Load parts list with PQt data"""
        try:
            # Start background thread for loading
            Thread(target=self._load_parts_background, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start data loading: {str(e)}")
    
    def _load_parts_background(self):
        """Background thread for loading parts"""
        try:
            query = """
                SELECT 
                    s.id,
                    s.spare_name,
                    s.material_type,
                    s.stock as system_qty,
                    COALESCE(p.physical_qty, s.stock) as physical_qty,
                    COALESCE(p.variance, 0) as variance,
                    s.rack_location,
                    COALESCE(DATE_FORMAT(p.check_date, '%Y-%m-%d'), 'Never') as last_check,
                    s.min_stock,
                    COALESCE(p.status, 'Pending') as pqt_status
                FROM spareparts s
                LEFT JOIN physical_quantity p ON s.id = p.spare_id
                ORDER BY 
                    CASE 
                        WHEN s.stock = 0 THEN 1
                        WHEN COALESCE(p.variance, 0) != 0 THEN 2
                        WHEN s.stock <= s.min_stock AND s.stock > 0 THEN 3
                        ELSE 4
                    END,
                    s.spare_name
            """
            results = Database.execute_query(query, fetch=True)
            
            # Update UI in main thread
            self.root.after(0, lambda: self.populate_tree(results))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load parts: {str(e)}"))
    
    def apply_filter(self):
        """Apply filter to parts list - OPTIMIZED"""
        filter_type = self.filter_var.get()
        search_term = self.search_var.get().lower()
        
        # Get all items first
        all_items = self.parts_tree.get_children()
        
        # Detach all items
        for item in all_items:
            self.parts_tree.detach(item)
        
        # Reattach matching items
        for item in all_items:
            values = self.parts_tree.item(item)['values']
            
            if len(values) < 3:
                continue
            
            name = str(values[1]).lower()
            material = str(values[2]).lower()
            status_icon = str(values[0])
            
            # Apply search filter
            if search_term and (search_term not in name and search_term not in material):
                continue
            
            # Apply type filter
            if self.should_show_item(filter_type, status_icon):
                self.parts_tree.reattach(item, '', 'end')
    
    def should_show_item(self, filter_type: str, status_icon: str) -> bool:
        """Determine if item should be shown based on filter"""
        if filter_type == "all":
            return True
        elif filter_type == "in_stock":
            return "✅" in status_icon
        elif filter_type == "low_stock":
            return "🟡" in status_icon
        elif filter_type == "out_of_stock":
            return "🔴" in status_icon
        elif filter_type == "needs_pqt":
            return "📊" in status_icon
        elif filter_type == "variance":
            return "⚠️" in status_icon or "❓" in status_icon
        return False
    
    def on_item_selected(self, event=None):
        """When item is selected from combobox"""
        item_name = self.item_combo.get()
        if not item_name:
            return
        
        try:
            query = """
                SELECT 
                    s.id,
                    s.product_number,
                    s.material_type,
                    s.stock as system_qty,
                    COALESCE(p.physical_qty, s.stock) as physical_qty,
                    COALESCE(p.variance, 0) as variance,
                    s.rack_location,
                    s.min_stock
                FROM spareparts s
                LEFT JOIN physical_quantity p ON s.id = p.spare_id
                WHERE s.spare_name = %s
            """
            result = Database.execute_query(query, (item_name,), fetch=True)
            
            if result and result[0]:
                spare_id, product_no, material, sys_qty, phy_qty, variance, rack, min_stock = result[0]
                
                # Update details labels
                self.detail_labels['item_no_label'].config(text=product_no or "-")
                self.detail_labels['material_label'].config(text=material or "-")
                self.detail_labels['system_qty_label'].config(text=str(sys_qty))
                self.detail_labels['physical_qty_label'].config(text=str(phy_qty))
                
                # Variance display with color
                variance_display = format_variance(variance)
                variance_label = self.detail_labels['variance_label']
                variance_label.config(text=variance_display)
                
                if variance > 0:
                    variance_label.config(fg="#28a745", font=('Segoe UI', 10, 'bold'))
                elif variance < 0:
                    variance_label.config(fg="#dc3545", font=('Segoe UI', 10, 'bold'))
                else:
                    variance_label.config(fg="#6c757d", font=('Segoe UI', 10))
                
                self.detail_labels['rack_label'].config(text=rack if rack else "Not Assigned")
                
                # Highlight if low stock
                sys_qty_label = self.detail_labels['system_qty_label']
                if sys_qty <= min_stock:
                    sys_qty_label.config(fg=self.colors['warning'], font=('Segoe UI', 10, 'bold'))
                else:
                    sys_qty_label.config(fg=self.colors['primary'], font=('Segoe UI', 10))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item details: {str(e)}")
    
    def on_tree_select(self, event):
        """When item is selected from treeview"""
        selected = self.parts_tree.selection()
        if not selected:
            return
            
        item = self.parts_tree.item(selected[0])
        item_name = item['values'][1]
        
        self.item_combo.set(item_name)
        self.on_item_selected()
    
    def on_tree_double_click(self, event):
        """Handle double-click on treeview item"""
        self.on_tree_select(event)
    
    def submit_transaction(self):
        """Submit pengambilan sparepart with PQt tracking"""
        # Get values
        item_name = self.item_combo.get()
        qty_str = self.qty_entry.get().strip()
        machine_name = self.machine_entry.get().strip()
        req_id = self.req_entry.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        # Validation
        if not all([item_name, qty_str, machine_name]):
            messagebox.showwarning("Validation", 
                                 "Please fill Item Name, Qty, and Machine Name!")
            return
        
        # Validate quantity
        is_valid, qty_used, error_msg = validate_integer(qty_str)
        if not is_valid:
            messagebox.showwarning("Validation", error_msg)
            self.qty_entry.focus_set()
            return
        
        try:
            conn = Database.get_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed!")
                return
            
            cursor = conn.cursor()
            
            # Get current stock
            cursor.execute("""
                SELECT id, product_number, stock 
                FROM spareparts 
                WHERE spare_name = %s
            """, (item_name,))
            result = cursor.fetchone()
            
            if not result:
                cursor.close()
                messagebox.showerror("Error", "Item not found!")
                return
            
            spare_id, product_no, current_stock = result
            
            # Check stock availability
            if qty_used > current_stock:
                cursor.close()
                messagebox.showerror("Insufficient Stock",
                                   f"Not enough system stock!\n\n"
                                   f"System Stock: {current_stock}\n"
                                   f"Requested: {qty_used}")
                return
            
            # Calculate new stock
            new_stock = current_stock - qty_used
            
            # Update spareparts stock
            cursor.execute("""
                UPDATE spareparts 
                SET stock = %s 
                WHERE id = %s
            """, (new_stock, spare_id))
            
            # Insert into stock_usage
            cursor.execute("""
                INSERT INTO stock_usage 
                (date_time, item_name, item_number, qty_stock, qty_used, machine_name, notes, issued_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (datetime.now(), item_name, product_no, current_stock, qty_used, machine_name, notes, "ME Operator"))
            
            # Update physical_quantity
            cursor.execute("""
                INSERT INTO physical_quantity 
                (spare_id, product_number, spare_name, system_qty, physical_qty, 
                 variance, checked_by, check_date, notes, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending')
                ON DUPLICATE KEY UPDATE
                system_qty = VALUES(system_qty),
                check_date = VALUES(check_date),
                notes = VALUES(notes)
            """, (spare_id, product_no, item_name, new_stock, new_stock, 0, "ME Operator", datetime.now(), notes))
            
            # Record movement
            cursor.execute("""
                INSERT INTO stock_movements 
                (spare_id, spare_name, movement_type, quantity, notes, created_by, created_at)
                VALUES (%s, %s, 'Out', %s, %s, %s, %s)
            """, (spare_id, item_name, qty_used, notes, "ME Operator", datetime.now()))
            
            conn.commit()
            cursor.close()
            
            # Success message
            success_msg = (
                f"✅ Sparepart taken successfully!\n\n"
                f"• Item: {item_name}\n"
                f"• Qty Taken: {qty_used}\n"
                f"• System Stock: {current_stock} → {new_stock}\n"
                f"• Machine: {machine_name}"
            )
            messagebox.showinfo("Success", success_msg)
            
            # Clear form and refresh data
            self.clear_form()
            self.load_parts_list()
            
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Transaction failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Transaction failed: {str(e)}")
    
    def clear_form(self):
        """Clear form fields"""
        self.qty_entry.delete(0, tk.END)
        self.machine_entry.delete(0, tk.END)
        self.req_entry.delete(0, tk.END)
        self.notes_text.delete("1.0", tk.END)
        self.qty_entry.focus_set()
    
    def open_admin_login(self):
        """Open admin login"""
        AdminLoginWindow(self).run()
    
    def open_pqt_check(self):
        """Open PQt check window"""
        messagebox.showinfo("PQt Check", "PQt Check feature coming soon!")
    
    def open_reports(self):
        """Open reports"""
        messagebox.showinfo("Reports", "Reports feature coming soon!")
    
    def export_data(self):
        """Export data to CSV"""
        messagebox.showinfo("Export", "Export feature coming soon!")
    
    def center_window(self):
        """Center window on screen"""
        center_window_on_screen(self.root)
    
    def on_closing(self):
        """Handle window closing"""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            Database.close_connection()
            self.root.destroy()
    
    def run(self):
        """Run application"""
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Error", f"Application error: {str(e)}")
        finally:
            Database.close_connection()


# ================================================
# ADMIN LOGIN WINDOW
# ================================================

class AdminLoginWindow:
    """Admin login window"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.root = tk.Toplevel() if parent else tk.Tk()
        self.root.title("🔐 ADMIN ACCESS")
        self.root.geometry("500x500")
        self.root.resizable(False, False)
        self.root.configure(bg='#f5f6fa')
        
        if parent:
            self.root.transient(parent.root)
            self.root.grab_set()
        
        # Create UI first
        self.create_ui()
        
        # Force center after all widgets are created
        self.root.update_idletasks()
        self.center_window()
        
        # Ensure window is visible and centered
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def center_window(self):
        """Center window on screen"""
        center_window_on_screen(self.root, 500, 500)
    
    def create_ui(self):
        """Create login UI"""
        main_frame = tk.Frame(self.root, bg='#f5f6fa')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Header
        header_frame = tk.Frame(main_frame, bg='#2c3e50', height=120)
        header_frame.pack(fill='x', pady=(0, 20))
        header_frame.pack_propagate(False)
        
        title_frame = tk.Frame(header_frame, bg='#2c3e50')
        title_frame.pack(expand=True)
        
        tk.Label(title_frame,
                text="🔐",
                font=('Segoe UI', 36),
                bg='#2c3e50',
                fg='white').pack()
        
        tk.Label(title_frame,
                text="ADMIN ACCESS",
                font=('Segoe UI', 20, 'bold'),
                bg='#2c3e50',
                fg='white').pack(pady=(5, 0))
        
        tk.Label(title_frame,
                text="Secure Administrative Login",
                font=('Segoe UI', 11),
                bg='#2c3e50',
                fg='#bdc3c7').pack()
        
        # Login form
        form_frame = tk.Frame(main_frame, bg='white', padx=30, pady=30)
        form_frame.pack(fill='both', expand=True)
        
        # Username
        tk.Label(form_frame,
                text="Username",
                font=('Segoe UI', 11, 'bold'),
                bg='white',
                fg='#2c3e50').pack(anchor='w', pady=(0, 5))
        
        self.username_entry = tk.Entry(form_frame,
                                      font=('Segoe UI', 12),
                                      width=30,
                                      relief='solid',
                                      bd=2)
        self.username_entry.pack(fill='x', pady=(0, 20))
        
        # Password
        tk.Label(form_frame,
                text="Password",
                font=('Segoe UI', 11, 'bold'),
                bg='white',
                fg='#2c3e50').pack(anchor='w', pady=(0, 5))
        
        password_frame = tk.Frame(form_frame, bg='white')
        password_frame.pack(fill='x', pady=(0, 20))
        
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(password_frame,
                                      textvariable=self.password_var,
                                      font=('Segoe UI', 12),
                                      width=30,
                                      show='•',
                                      relief='solid',
                                      bd=2)
        self.password_entry.pack(side='left', fill='x', expand=True)
        
        self.show_password = False
        self.toggle_btn = tk.Button(password_frame,
                                   text="👁️",
                                   command=self.toggle_password,
                                   bg='#ecf0f1',
                                   fg='#7f8c8d',
                                   font=('Segoe UI', 10),
                                   relief='flat',
                                   cursor='hand2',
                                   width=4)
        self.toggle_btn.pack(side='right', padx=(10, 0))
        
        # Error label
        self.error_label = tk.Label(form_frame,
                                   text="",
                                   font=('Segoe UI', 10),
                                   bg='white',
                                   fg='#e74c3c',
                                   height=2)
        self.error_label.pack(fill='x', pady=(0, 10))
        
        # Login button
        self.login_btn = tk.Button(form_frame,
                                  text="🔓 LOGIN",
                                  command=self.do_login,
                                  bg='#3498db',
                                  fg='white',
                                  font=('Segoe UI', 12, 'bold'),
                                  relief='flat',
                                  cursor='hand2',
                                  height=2,
                                  width=20)
        self.login_btn.pack(pady=(0, 20))
        
        # Footer
        footer_frame = tk.Frame(main_frame, bg='#f5f6fa')
        footer_frame.pack(fill='x')
        
        if self.parent:
            back_btn = tk.Button(footer_frame,
                                text="← Back to Main",
                                command=self.back_to_main,
                                bg='#95a5a6',
                                fg='white',
                                font=('Segoe UI', 10),
                                relief='flat',
                                cursor='hand2',
                                padx=15,
                                pady=8)
            back_btn.pack()
        
        self.username_entry.focus_set()
        self.password_entry.bind('<Return>', lambda e: self.do_login())
        self.root.bind('<Escape>', lambda e: self.root.destroy())
    
    def toggle_password(self):
        """Toggle password visibility"""
        self.show_password = not self.show_password
        if self.show_password:
            self.password_entry.config(show='')
            self.toggle_btn.config(text="🙈")
        else:
            self.password_entry.config(show='•')
            self.toggle_btn.config(text="👁️")
    
    def do_login(self):
        """Authenticate admin"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        self.error_label.config(text="")
        
        if not username:
            self.error_label.config(text="⚠️ Please enter username")
            self.username_entry.focus_set()
            return
        
        if not password:
            self.error_label.config(text="⚠️ Please enter password")
            self.password_entry.focus_set()
            return
        
        # Simple authentication
        valid_users = {
            "admin": "admin123",
            "user": "user123",
            "me": "me123"
        }
        
        if username in valid_users and valid_users[username] == password:
            self.error_label.config(text="✅ Login successful!", fg='#27ae60')
            self.login_btn.config(text="✅ ACCESS GRANTED", bg='#27ae60')
            self.root.after(1000, self.login_successful)
        else:
            self.error_label.config(text="❌ Invalid username or password")
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()
    
    def login_successful(self):
        """Handle successful login"""
        messagebox.showinfo("Admin Access", "Welcome to Admin Panel!")
        self.root.destroy()
    
    def back_to_main(self):
        """Return to main application"""
        self.root.destroy()
        if self.parent:
            self.parent.root.deiconify()
    
    def run(self):
        """Run login window"""
        self.root.mainloop()


# ================================================
# SAMPLE DATA CREATION - OPTIMIZED
# ================================================

def create_sample_data():
    """Create sample data if tables are empty"""
    try:
        result = Database.execute_query("SELECT COUNT(*) FROM spareparts", fetch=True)
        
        if result and result[0][0] == 0:
            print("Creating sample data...")
            
            sample_spareparts = [
                ("B001", "Bearing 6205", "Steel", 50, 5, "Rack A-01"),
                ("B002", "Bearing 6306", "Steel", 30, 3, "Rack A-02"),
                ("S001", "Seal 25x42x7", "Rubber", 100, 10, "Rack B-01"),
                ("B003", "Belt B-85", "Rubber", 20, 2, "Rack B-02"),
                ("O001", "Oil Filter", "Paper/Metal", 40, 4, "Rack C-01"),
                ("G001", "Gasket Set", "Rubber", 60, 6, "Rack C-02"),
                ("P001", "Pump Seal", "Ceramic", 25, 3, "Rack D-01"),
                ("V001", "Valve Assembly", "Brass", 15, 2, "Rack D-02"),
                ("M001", "Motor Coupling", "Steel", 35, 4, "Rack E-01"),
                ("C001", "Chain Sprocket", "Steel", 45, 5, "Rack E-02"),
            ]
            
            # Batch insert
            query = """
                INSERT INTO spareparts 
                (product_number, spare_name, material_type, stock, min_stock, rack_location)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            Database.execute_many(query, sample_spareparts)
            
            print(f"Inserted {len(sample_spareparts)} sample items")
            
    except Exception as e:
        print(f"Sample data creation error: {e}")


# ================================================
# MAIN ENTRY POINT - OPTIMIZED
# ================================================

def main():
    """Main entry point with loading screen"""
    try:
        # Show loading screen
        loading = LoadingScreen()
        loading.update_status("Connecting to database...")
        loading.root.update()
        
        # Setup database
        Database.setup_database()
        
        loading.update_status("Creating sample data...")
        loading.root.update()
        
        # Create sample data
        create_sample_data()
        
        loading.update_status("Starting application...")
        loading.root.update()
        
        # Create main application
        app = SparepartApp(loading)
        app.run()
        
    except Exception as e:
        print(f"Application error: {e}")
        traceback.print_exc()
        messagebox.showerror("Fatal Error", f"Application failed to start:\n\n{str(e)}")
    finally:
        Database.close_connection()

if __name__ == "__main__":
    main()