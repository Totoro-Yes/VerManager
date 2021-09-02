CHCP 65001

try {
    Invoke-Expression $args[0]
} catch {
    exit 1
}

exit 0