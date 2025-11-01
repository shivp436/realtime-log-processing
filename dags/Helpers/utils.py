import re
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class LogParser:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Apache Combined Log Format regex pattern
        # Format: %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"
        self.apache_combined_pattern = re.compile(
            r'^'
            r'(?P<ip_address>\S+) '                    # %h - remote host (IP)
            r'(?P<identd>\S+) '                       # %l - identd (usually -)
            r'(?P<auth_user>\S+) '                    # %u - auth user
            r'\[(?P<timestamp>[^\]]+)\] '             # %t - timestamp
            r'"(?P<method>\S+) '                      # %r - request method
            r'(?P<endpoint>\S+) '                     # %r - endpoint
            r'(?P<http_version>HTTP/\d\.\d)" '        # %r - HTTP version
            r'(?P<status_code>\d{3}) '                # %>s - status code
            r'(?P<response_size>\d+) '                # %b - response size
            r'"(?P<referrer>[^"]*)" '                 # %{Referer}i - referrer
            r'"(?P<user_agent>[^"]*)"'                # %{User-Agent}i - user agent
            r'$'
        )
        self.logger.info("Log Parser initialized")

    def parse_log(self, log_entry):
        """
        Parse a single log entry in Apache Combined Log Format
        
        Args:
            log_entry (str): Log entry string
            
        Returns:
            dict: Parsed log fields or None if parsing fails
        """
        try:
            match = self.apache_combined_pattern.match(log_entry.strip())
            
            if not match:
                self.logger.warning(f"Failed to parse log entry: {log_entry}")
                return None
            
            fields = match.groupdict()
            
            # Convert numeric fields to appropriate types
            fields['status_code'] = int(fields['status_code'])
            fields['response_size'] = int(fields['response_size'])
            
            # Handle dash values (meaning empty/null)
            if fields['identd'] == '-':
                fields['identd'] = None
            if fields['auth_user'] == '-':
                fields['auth_user'] = None
            if fields['referrer'] == '-':
                fields['referrer'] = None
            
            self.logger.debug(f"Successfully parsed log entry: {fields['ip_address']} - {fields['method']} {fields['endpoint']}")
            
            return fields
            
        except Exception as e:
            self.logger.error(f"Error parsing log entry: {e}")
            return None

    def parse_logs(self, log_entries):
        """
        Parse multiple log entries
        
        Args:
            log_entries (list): List of log entry strings
            
        Returns:
            list: List of parsed log dictionaries
        """
        parsed_logs = []
        
        for log_entry in log_entries:
            parsed = self.parse_log(log_entry)
            if parsed:
                parsed_logs.append(parsed)
        
        self.logger.info(f"Parsed {len(parsed_logs)} out of {len(log_entries)} log entries")
        return parsed_logs
