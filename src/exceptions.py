class MFARequiredException(Exception):
    def __init__(self, message="MFA code is required.", mfa_data=None):
        super().__init__(message)
        self.mfa_data = mfa_data # mfa_data will likely be the 'ticket'