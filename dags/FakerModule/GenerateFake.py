from faker import Faker
import random
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger('faker').setLevel(logging.WARNING)

class GenerateFakeWebsiteLog:
    def __init__(self):
        self.fake = Faker()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Fake Website Log Generator initialized")
    
    def _get_ip_address(self):
        """Generate IP address"""
        return self.fake.ipv4()
    
    def _get_auth_user(self):
        """Generate authenticated user or '-' for none"""
        return self.fake.user_name() if random.random() > 0.3 else "-"
    
    def _get_timestamp(self):
        """Generate timestamp in Apache format"""
        return datetime.now().strftime("[%d/%b/%Y:%H:%M:%S +0000]")
    
    def _get_http_method(self):
        """Generate HTTP method"""
        return random.choice(["GET", "POST", "PUT", "DELETE", "HEAD"])
    
    def _get_endpoint(self):
        """Generate realistic endpoint"""
        endpoints = [
            "/", "/home", "/index.html", "/about", "/contact",
            "/products", "/products/item123", "/products/item456",
            "/api/v1/users", "/api/v1/products", "/login", "/logout",
            "/search", "/cart", "/checkout", "/profile", "/settings"
        ]
        return random.choice(endpoints)
    
    def _get_http_version(self):
        """Generate HTTP version"""
        return random.choice(["HTTP/1.0", "HTTP/1.1", "HTTP/2.0"])
    
    def _get_status_code(self):
        """Generate HTTP status code with realistic distribution"""
        codes_weights = [
            (200, 0.70),  # Success
            (301, 0.05),  # Moved permanently
            (302, 0.05),  # Found/redirect
            (304, 0.03),  # Not modified
            (400, 0.04),  # Bad request
            (401, 0.02),  # Unauthorized
            (403, 0.02),  # Forbidden
            (404, 0.06),  # Not found
            (500, 0.03),  # Internal server error
        ]
        codes, weights = zip(*codes_weights)
        return random.choices(codes, weights=weights)[0]
    
    def _get_response_size(self, status_code):
        """Generate realistic response size based on status code"""
        if status_code == 200:
            return random.randint(500, 10000)  # Successful response
        elif status_code in [301, 302]:
            return random.randint(200, 500)    # Redirect
        elif status_code == 304:
            return 0                           # Not modified
        elif status_code in [400, 401, 403, 404]:
            return random.randint(200, 2000)   # Client error
        else:
            return random.randint(100, 1000)   # Server error
    
    def _get_referrer(self):
        """Generate referrer URL"""
        if random.random() > 0.4:  # 60% chance of having a referrer
            return f"https://{self.fake.domain_name()}{self._get_endpoint()}"
        return "-"
    
    def _get_user_agent(self):
        """Generate realistic user agent"""
        browsers = [
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]
        return random.choice(browsers)
    
    def get_log(self):
        """Generate a fake log entry in Apache Combined Log Format"""
        
        ip_address = self._get_ip_address()
        identd_user = "-"  # Always dash for identd
        auth_user = self._get_auth_user()
        timestamp = self._get_timestamp()
        http_method = self._get_http_method()
        endpoint = self._get_endpoint()
        http_version = self._get_http_version()
        status_code = self._get_status_code()
        response_size = self._get_response_size(status_code)
        referrer = self._get_referrer()
        user_agent = self._get_user_agent()
        
        # Build the log entry in Apache Combined Log Format
        log_entry = f'{ip_address} {identd_user} {auth_user} {timestamp} "{http_method} {endpoint} {http_version}" {status_code} {response_size} "{referrer}" "{user_agent}"'
        
        return log_entry
