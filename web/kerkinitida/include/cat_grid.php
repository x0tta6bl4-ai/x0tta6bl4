<ul id="block_grid">
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
								$max_width = 200;
								$max_height = 150;
								list($width, $height) = getimagesize($img_path);
								$ratioh = $max_height/$height;
								$ratiow = $max_width/$width;
								$ratio = min($ratioh, $ratiow);
								$width = intval($ratio*$width);
								$height = intval($ratio*$height);
							}else
								{
									$img_path = "../img/noimage.jpg";
									$width=200;
									$height=150;
								}
			$images = '';
			if($row['wifi'] == 1) $images  .= '<img src="/img/wifi.png" />';
			if($row['conditioner'] == 1) $images  .= '<img src="/img/condition.png" />';
			if($row['yard'] == 1) $images  .= '<img src="/img/yard.png" />';
			if($row['parking'] == 1) $images  .= '<img src="/img/parking.png" />';
			
			echo '
				<li>
					<div class="images_grid"><img src="'.$img_path.'" width='.$width.' height='.$height.'/></div>
					<p class="title_grid"><a href="view_cat.php?id='.$row["option_id"].'">'.$row["title"].'</a></p>
					<p class="price_grid"><strong>'.$row["price"].'</strong> рублей</p>
					<div class="comfort_grid">' . $images . '</div>
					<div class="mini_description">'.$row["mini_description"].'</div>
				</li>
			';
		}
			while ($row = mysql_fetch_array($result));
	}
?>
</ul>