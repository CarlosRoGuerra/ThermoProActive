from rest_framework.throttling import AnonRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = "auth_login"


class RecoveryThrottle(AnonRateThrottle):
    scope = "auth_recovery"


class OtpThrottle(AnonRateThrottle):
    scope = "auth_otp"


class RegistrationThrottle(AnonRateThrottle):
    scope = "auth_registration"
