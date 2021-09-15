CHCP 65001

try {
    Invoke-Expression $args[0]
    if ($? -ne 0) {
       exit 1
    }
} catch {
    exit 1
}

exit 0