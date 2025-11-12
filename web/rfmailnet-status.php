<?php
header('Content-Type: text/html; charset=utf-8');
$hub_file = '/var/www/vk2icw/assets/rfmailnet-hub.json';
$node_file = '/var/www/vk2icw/assets/rfmailnet-node.json';

function load_json($file) {
    if (file_exists($file)) {
        return json_decode(file_get_contents($file), true);
    } else {
        return ["error" => "File not found: $file"];
    }
}

$hub = load_json($hub_file);
$node = load_json($node_file);
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RFMailNet Status Dashboard</title>
<style>
body { font-family: Arial, sans-serif; background:#111; color:#eee; text-align:center; }
table { margin:20px auto; border-collapse:collapse; width:80%; }
th, td { border:1px solid #444; padding:10px; }
th { background:#222; }
td { background:#1a1a1a; }
h1 { color:#00bcd4; }
.error { color: #ff6666; }
</style>
</head>
<body>
<h1>RFMailNet Status Dashboard</h1>

<h2>Hub Status</h2>
<table>
<?php
if (isset($hub['error'])) {
    echo "<tr><td class='error'>{$hub['error']}</td></tr>";
} else {
    foreach ($hub as $key => $value) {
        echo "<tr><th>$key</th><td>$value</td></tr>";
    }
}
?>
</table>

<h2>Node Status</h2>
<table>
<?php
if (isset($node['error'])) {
    echo "<tr><td class='error'>{$node['error']}</td></tr>";
} else {
    foreach ($node as $key => $value) {
        echo "<tr><th>$key</th><td>$value</td></tr>";
    }
}
?>
</table>
</body>
</html>
