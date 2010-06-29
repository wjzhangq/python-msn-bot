<?php
if (isset($argv[1])){
	$tmp = urldecode($argv[1]);
	$arr = explode("\n\r\n", $tmp);
	file_put_contents('a.log', "\n" . date('Y-m-d H:i:s') . "\r" . var_export($arr, true), FILE_APPEND);
}

?>