from PIL import Image

def merge_horizontal(img_path1, img_path2, output_path, gap=20):
    img1 = Image.open(img_path1)
    img2 = Image.open(img_path2)

    max_h = max(img1.height, img2.height)
    img1 = img1.resize((int(img1.width * max_h / img1.height), max_h))
    img2 = img2.resize((int(img2.width * max_h / img2.height), max_h))

    total_w = img1.width + gap + img2.width
    result = Image.new("RGB", (total_w, max_h), "white")
    result.paste(img1, (0, 0))
    result.paste(img2, (img1.width + gap, 0))
    result.save(output_path)
    print(f"拼接完成: {output_path} ({total_w}x{max_h})")

merge_horizontal("1.png", "2.png", "merged_1_2.png")
