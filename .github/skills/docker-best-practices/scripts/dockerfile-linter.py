#!/usr/bin/env python3
"""
Dockerfile linter for best practices.
Checks for common security, performance, and maintainability issues.
"""

import re
import sys
from pathlib import Path


class DockerfileLinter:
    def __init__(self, dockerfile_path):
        self.path = Path(dockerfile_path)
        self.lines = self.path.read_text().split('\n')
        self.issues = []
        self.warnings = []

    def lint(self):
        self.check_base_image()
        self.check_layer_caching()
        self.check_user()
        self.check_cmd_format()
        self.check_secrets()
        self.check_healthcheck()
        self.check_root_operations()
        self.check_cleanup()
        return self.issues, self.warnings

    def check_base_image(self):
        """Check if base image uses latest or vague version."""
        for i, line in enumerate(self.lines, 1):
            if line.strip().startswith('FROM'):
                if ':latest' in line or (':' not in line and 'scratch' not in line and 'busybox' not in line):
                    self.issues.append(f"Line {i}: Base image uses 'latest' or no version tag")
                if 'ubuntu:22.04' in line or 'ubuntu:20.04' in line or 'debian' in line:
                    self.warnings.append(f"Line {i}: Consider using '-slim' or '-alpine' variant for smaller image")

    def check_layer_caching(self):
        """Check if Dockerfile follows cache-optimal ordering."""
        copy_seen = False
        run_after_copy = False
        
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if stripped.startswith('COPY') and 'requirements.txt' not in line and 'package' not in line:
                copy_seen = True
            elif stripped.startswith('RUN') and copy_seen:
                run_after_copy = True
                break
        
        if run_after_copy:
            self.warnings.append("Consider copying dependency files before application code for better layer caching")

    def check_user(self):
        """Check if non-root user is created."""
        user_found = False
        for line in self.lines:
            if 'USER' in line and 'appuser' in line or 'nobody' in line:
                user_found = True
                break
        
        if not user_found:
            self.issues.append("No non-root user found. Add 'RUN useradd -m appuser' and 'USER appuser'")

    def check_cmd_format(self):
        """Check if CMD uses exec form (array syntax)."""
        for i, line in enumerate(self.lines, 1):
            if line.strip().startswith('CMD'):
                if 'CMD [' not in line:
                    self.issues.append(f"Line {i}: CMD should use exec form (array syntax): CMD [\"command\", \"arg\"]")

    def check_secrets(self):
        """Check for hardcoded secrets."""
        secret_patterns = [
            r'ENV\s+.*PASSWORD\s*=',
            r'ENV\s+.*TOKEN\s*=',
            r'ENV\s+.*KEY\s*=',
            r'ENV\s+.*SECRET\s*=',
        ]
        
        for i, line in enumerate(self.lines, 1):
            for pattern in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Exclude if value is a placeholder
                    if '${' not in line and '$(' not in line:
                        self.issues.append(f"Line {i}: Do not hardcode secrets in ENV variables")

    def check_healthcheck(self):
        """Check if HEALTHCHECK is present."""
        healthcheck_found = any('HEALTHCHECK' in line for line in self.lines)
        if not healthcheck_found:
            self.warnings.append("Consider adding HEALTHCHECK for production containers")

    def check_root_operations(self):
        """Check if file operations use root unnecessarily."""
        for i, line in enumerate(self.lines, 1):
            if 'RUN' in line and ('chown' in line or 'chmod' in line):
                # Check if it's after USER declaration
                remaining = self.lines[i:]
                user_after = any('USER' in l for l in remaining)
                if not user_after:
                    self.warnings.append(f"Line {i}: File ownership set before USER declaration")

    def check_cleanup(self):
        """Check if package caches are cleaned."""
        for i, line in enumerate(self.lines, 1):
            if 'apt-get install' in line:
                # Check if same RUN cleans cache
                if i < len(self.lines) and 'rm -rf /var/lib/apt/lists' not in '\n'.join(self.lines[i:i+5]):
                    self.warnings.append(f"Line {i}: apt-get install should clean cache in same RUN: && rm -rf /var/lib/apt/lists/*")

    def report(self):
        """Print formatted report."""
        print(f"\n=== Dockerfile Linter Report: {self.path} ===\n")
        
        if self.issues:
            print(f"❌ ERRORS ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   • {issue}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if not self.issues and not self.warnings:
            print("✅ No issues found!")
        
        print()
        return len(self.issues) == 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 dockerfile-linter.py <Dockerfile>")
        sys.exit(1)
    
    linter = DockerfileLinter(sys.argv[1])
    issues, warnings = linter.lint()
    success = linter.report()
    sys.exit(0 if success else 1)
