import enum


class ScopeType(str, enum.Enum):
    GROUP = "group"
    CHANNEL = "channel"
    DIRECT = "direct"


class ReceiptStatus(str, enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


STATUS_RANK = {
    ReceiptStatus.SENT: 1,
    ReceiptStatus.DELIVERED: 2,
    ReceiptStatus.READ: 3,
}
