<?

function createThumbnail($filename) {
	
	require 'config.php'; //Ïîäêëş÷àåì ôàéë êîíôèãóğàöèè
	
	if(preg_match('/[.](jpg)$/', $filename)) {
		$im = imagecreatefromjpeg($path_to_image_directory . $filename);
	} else if (preg_match('/[.](gif)$/', $filename)) {
		$im = imagecreatefromgif($path_to_image_directory . $filename);
	} else if (preg_match('/[.](png)$/', $filename)) {
		$im = imagecreatefrompng($path_to_image_directory . $filename);
	} //Îïğåäåëÿåì ôîğìàò èçîáğàæåíèÿ
	
	$ox = imagesx($im);
	$oy = imagesy($im);
	
	$nx = $final_width_of_image;
	$ny = floor($oy * ($final_width_of_image / $ox));
	
	$nm = imagecreatetruecolor($nx, $ny);
	
	imagecopyresized($nm, $im, 0,0,0,0,$nx,$ny,$ox,$oy);
	
	if(!file_exists($path_to_thumbs_directory)) {
	  if(!mkdir($path_to_thumbs_directory)) {
           die("Âîçíèêëè ïğîáëåìû! ïîïğîáóéòå ñíîâà!");
	  } 
       }

	imagejpeg($nm, $path_to_thumbs_directory . $filename);
	$tn = '<img src="' . $path_to_thumbs_directory . $filename . '" alt="image" />';
	$tn .= '<br />Ïîçäğàâëÿåì! Âàøå èçîáğàæåíèå óñïåøíî çàãğóæåíî è åãî ìèíèàòşğà óäà÷íî âûïîëíåíà. Âûøå Âû ìîæåòå ïğîñìîòğåòü ğåçóëüòàò:';
	echo $tn;
}//Ñæèìàåì èçîáğàæåíèå, åñëè åñòü îèøèáêè, òî ãîâîğèì î íèõ, åñëè èõ íåò, òî âûâîäèì ïîëó÷èâøóşñÿ ìèíèàòşğó


?>