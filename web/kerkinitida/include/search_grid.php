<ul id="block_grid">
<?php		
		$queries = array();
		
		if(!empty($_GET['card']))
		{
			$card = mysql_real_escape_string(strip_tags($_GET['card']));
			$queries[] = "`card` = '$card'";
		}
		
		if(!empty($_GET['price']))
		{
			$price = explode(';', $_GET['price']);
			
			if(!empty($price[0]) and !empty($price[1]))
				$queries[] = '`price` BETWEEN ' . (int) $price[0] . ' AND ' . (int) $price[1];
		}
		
		if(!empty($_GET['distance']))
		{
			$distance = explode(';', $_GET['distance']);
			
			if(!empty($distance[0]) and !empty($distance[1]))
				$queries[] = '`distance` BETWEEN ' . (int) $distance[0] . ' AND ' . (int) $distance[1];
		}		
		
		if(!empty($_GET['amount']))
		{
			$queries[] = '`amount` >= ' . (int) $_GET['amount'];
		}

        if(!empty($_GET['wifi'])) 		$queries[] = '`wifi` = 1';
        if(!empty($_GET['conditioner'])) 	$queries[] = '`conditioner` = 1';
        if(!empty($_GET['yard']))			$queries[] = '`yard` = 1';
        if(!empty($_GET['parking']))		$queries[] = '`parking` = 1';
        
		$where = '';
		
        foreach($queries as $key => $value)
		{
            if(empty($where))
				$where = 'WHERE ' . $value;
			else{
				$where .= ' AND ' . $value;
			}
        }
      		
		$query = 'SELECT * FROM `table_option` ' . $where;
		$result = mysql_query($query) or die(mysql_error());
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