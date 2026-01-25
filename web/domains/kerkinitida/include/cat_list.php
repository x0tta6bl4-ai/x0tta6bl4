<ul id="block_list">
<?php
	if (!empty($card))
	{
		$querycard = "AND card='$card'";
	}else
	{
		$querycard = "";
	}		
	$result = mysql_query("SELECT * FROM table_option WHERE visible='1' $querycard ORDER BY $sorting",$link);
	if(mysql_num_rows($result) > 0)
	{
		$row = mysql_fetch_array($result);
		do
		{
			if ($row["image"] !="" && file_exists("./uploads_images/".$row["image"]))
							{
								$img_path='./uploads_images/'.$row["image"];
								$max_width = 300;
								$max_height = 200;
								list($width, $height) = getimagesize($img_path);
								$ratioh = $max_height/$height;
								$ratiow = $max_width/$width;
								$ratio = min($ratioh, $ratiow);
								$width = intval($ratio*$width);
								$height = intval($ratio*$height);
							}else
								{
									$img_path = "../img/noimage.jpg";
									$max_width = 300;
									$max_height = 200;
								}
			$images = '';
			if($row['wifi'] == 1) $images  .= '<img src="/img/wifi.png" />';
			if($row['conditioner'] == 1) $images  .= '<img src="/img/condition.png" />';
			if($row['yard'] == 1) $images  .= '<img src="/img/yard.png" />';
			if($row['parking'] == 1) $images  .= '<img src="/img/parking.png" />';
			echo '
				
				<li>
					<div class="images_list"><img src="'.$img_path.'" width='.$width.' height='.$height.'/></div>
					<p class="title_list"><a href="view_cat.php?id='.$row["option_id"].'">'.$row["title"].'</a></p>
					<div class="comfort_list">' . $images . '</div>
					<p class="price_list"><strong>'.$row["price"].'</strong> руб.</p>
					<div class="description">'.$row["description"].'</div>
				</li>
			';
		}
			while ($row = mysql_fetch_array($result));
	}
?>
</ul>