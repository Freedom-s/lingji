import torch
import numpy as np
import logging

from PIL import Image
from scipy import special
from typing import List
from qwen_vl_utils import process_vision_info
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

logger = logging.getLogger(__name__)

MAX_LENGTH = 8192 # 模型单次处理的最大token数量
IMAGE_BASE_FACTOR = 16 # 16*16个像素的小patch
IMAGE_FACTOR = IMAGE_BASE_FACTOR * 2 #qwen3vl做了动态合并，就是32*32=1024，也就是说1024个像素，就会消耗掉1个token
MIN_PIXELS = 4 * IMAGE_FACTOR * IMAGE_FACTOR  # 4 tokens。最小的像素是4*1024 = 2048
MAX_PIXELS = 1280 * IMAGE_FACTOR * IMAGE_FACTOR  # 1280 tokens。 最大的像素是1280*1024 = 131w，大约是一张比较1144x1144
MAX_RATIO = 200 # 图片的最大宽高比

FRAME_FACTOR = 2 # 视频事件轴上的压缩系数。
FPS = 1 # 默认情况下，无论是视频是高清还是超清，即30帧/s或者60帧/s，默认情况下每秒只有1帧图像，因为理解视频的大概意思足够
MIN_FRAMES = 2 # 一个视频最少有2帧图片
MAX_FRAMES = 64 # 一个2h的电影，最终会被抽出来7200帧，但是呢，只能均匀的抽搐64帧
MIN_TOTAL_PIXELS = 1 * FRAME_FACTOR * MIN_PIXELS  # 1 frames
MAX_TOTAL_PIXELS = 4 * FRAME_FACTOR * MAX_PIXELS  # 4 frames # 一个视频抽出来的帧图片，最多只能是8个顶级的像素，即8*1280


def sample_frames(frames, num_segments, max_segments):
    duration = len(frames)
    # 均匀的生成64个点，取这64个点中的帧图像。即均匀抽帧
    frame_id_array = np.linspace(0, duration - 1, num_segments, dtype=int)
    frame_id_list = frame_id_array.tolist()
    last_frame_id = frame_id_list[-1]

    sampled_frames = []
    for frame_idx in frame_id_list:
        try:
            single_frame_path = frames[frame_idx]
        except:
            break
        sampled_frames.append(single_frame_path)
    # Pad with last frame if total frames less than num_segments
    while len(sampled_frames) < num_segments:
        sampled_frames.append(frames[last_frame_id])
    return sampled_frames[:max_segments]

def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

class Qwen3VLReranker():
    def __init__(
        self,
        model_name_or_path: str,
        max_length: int = MAX_LENGTH,
        min_pixels: int = MIN_PIXELS,
        max_pixels: int = MAX_PIXELS,
        total_pixels: int = MAX_TOTAL_PIXELS,
        fps: float = FPS,
        num_frames: int = MAX_FRAMES,
        max_frames: int = MAX_FRAMES,
        default_instruction: str = "Given a search query, retrieve relevant candidates that answer the query.",
        **kwargs,
    ):

        self.device = get_device()
        print(f"using device:{self.device}")
        self.max_length = max_length
        self.min_pixels = min_pixels
        self.max_pixels = max_pixels
        self.total_pixels = total_pixels
        self.fps = fps
        self.num_frames = num_frames
        self.max_frames = max_frames

        self.default_instruction = default_instruction

        lm = Qwen3VLForConditionalGeneration.from_pretrained(
            model_name_or_path,
            trust_remote_code=True, **kwargs
        ).to(self.device)

        self.model = lm.model
        self.processor = AutoProcessor.from_pretrained(
            model_name_or_path, trust_remote_code=True,
            padding_side='left'
        )
        self.model.eval()

        token_true_id = self.processor.tokenizer.get_vocab()["yes"]
        token_false_id = self.processor.tokenizer.get_vocab()["no"]
        self.score_linear = self.get_binary_linear(lm, token_true_id, token_false_id)
        self.score_linear.eval()
        self.score_linear.to(self.device).to(self.model.dtype)

    def get_binary_linear(self, model, token_yes, token_no):

        """这里做的其实是一个二分类问题，用于判断yes/no的概率"""
        lm_head_weights = model.lm_head.weight.data

        weight_yes = lm_head_weights[token_yes]
        weight_no = lm_head_weights[token_no]

        D = weight_yes.size()[0]
        linear_layer = torch.nn.Linear(D, 1, bias=False)
        with torch.no_grad():
            linear_layer.weight[0] = weight_yes - weight_no
        return linear_layer

    @torch.no_grad()
    def compute_scores(self, inputs):
        # 取hidden_size的最后一个token
        batch_scores = self.model(**inputs).last_hidden_state[:, -1]
        scores = self.score_linear(batch_scores)
        scores = torch.sigmoid(scores).squeeze(-1).cpu().detach().tolist()
        return scores

    def truncate_tokens_optimized(
        self,
        tokens: List[str],
        max_length: int,
        special_tokens: List[str]
    ) -> List[str]:
        if len(tokens) <= max_length:
            return tokens

        special_tokens_set = set(special_tokens)

        # Calculate budget: how many non-special tokens we can keep
        num_special = sum(1 for token in tokens if token in special_tokens_set)
        num_non_special_to_keep = max_length - num_special

        # Build final list according to budget
        final_tokens = []
        non_special_kept_count = 0
        for token in tokens:
            if token in special_tokens_set:
                final_tokens.append(token)
            elif non_special_kept_count < num_non_special_to_keep:
                final_tokens.append(token)
                non_special_kept_count += 1

        return final_tokens

    def tokenize(self, pairs: list, **kwargs):
        max_length = self.max_length
        text = self.processor.apply_chat_template(pairs, tokenize=False, add_generation_prompt=True)
        try:
            images, videos, video_kwargs = process_vision_info(
                pairs, image_patch_size=16, 
                return_video_kwargs=True, 
                return_video_metadata=True
            )
        except Exception as e:
            logger.error(f"Error in processing vision info: {e}")
            images = None
            videos = None
            video_kwargs = {'do_sample_frames': False}
            text = self.processor.apply_chat_template(
                [{'role': 'user', 'content': [{'type': 'text', 'text': 'NULL'}]}], 
                add_generation_prompt=True, tokenize=False
            )
        
        if videos is not None:
            videos, video_metadatas = zip(*videos)
            videos, video_metadatas = list(videos), list(video_metadatas)
        else:
            video_metadatas = None
        inputs = self.processor(
            text=text,
            images=images,
            videos=videos,
            video_metadata=video_metadatas,
            truncation=False,
            padding=False,
            do_resize=False,
            **video_kwargs
        )
        for i, ele in enumerate(inputs['input_ids']):
            inputs['input_ids'][i] = self.truncate_tokens_optimized(
                inputs['input_ids'][i][:-5], max_length,
                self.processor.tokenizer.all_special_ids
            ) + inputs['input_ids'][i][-5:]
        temp_inputs = self.processor.tokenizer.pad(
            {'input_ids': inputs['input_ids']}, padding=True,
            return_tensors="pt", max_length=self.max_length
        )
        for key in temp_inputs:
            inputs[key] = temp_inputs[key]
        return inputs

    def format_mm_content(
        self, 
        text, image, video, 
        prefix='Query:', 
        fps=None, max_frames=None,
    ):
        """
        return结果:
        content = [
            {'type': 'text', 'text': "<Query>:"},
            {'type': 'video', 'video': "这里既可以是一个列表list，也可以是一个str", **video_kwargs},
            {'type': 'image', 'image': "这里的image_content既可以是一个image.image对象，也可以是一个str路径","min_pixels": self.min_pixels,"max_pixels": self.max_pixels},
            {'type': 'text', 'text': text}
        ]
        """
        content = []

        content.append({'type': 'text', 'text': prefix})
        if not text and not image and not video:
            content.append({'type': 'text', 'text': "NULL"})
            return content

        if video:
            # TODO：bug，这里又个bug，处理视频的时候并没有这个函数_sample_frames。视频，本质上就是一对连续的图片
            video_content = None
            video_kwargs = { 'total_pixels': self.total_pixels }
            if isinstance(video, list):
                video_content = video
                if self.num_frames is not None or self.max_frames is not None:
                    video_content = sample_frames(video_content, self.num_frames, self.max_frames)
                video_content = [
                    ('file://' + ele if isinstance(ele, str) else ele) 
                    for ele in video_content
                ]
            elif isinstance(video, str):
                video_content = video if video.startswith(('http://', 'https://')) else 'file://' + video
                video_kwargs = {'fps': fps or self.fps, 'max_frames': max_frames or self.max_frames,}
            else:
                raise TypeError(f"Unrecognized video type: {type(video)}")

            if video_content:
                content.append({
                    'type': 'video', 'video': video_content,
                    **video_kwargs
                })

        if image:
            image_content = None
            if isinstance(image, Image.Image):
                image_content = image
            elif isinstance(image, str):
                image_content = image if image.startswith(('http', 'oss')) else 'file://' + image
            else:
                raise TypeError(f"Unrecognized image type: {type(image)}")

            if image_content:
                content.append({
                    'type': 'image', 'image': image_content,
                    "min_pixels": self.min_pixels,
                    "max_pixels": self.max_pixels
                })

        if text:
            content.append({'type': 'text', 'text': text})
        return content

    def format_mm_instruction(
        self, 
        query_text, query_image, query_video, 
        doc_text, doc_image, doc_video,
        instruction=None, 
        fps=None, max_frames=None
    ):
        """
        return结果
        input = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text":"<Instruct>: Retrieve images or text relevant to the user's query."},
                    # query信息
                    {'type': 'text', 'text': "<Query>:"},
                    {'type': 'video', 'video': "这里既可以是一个列表list，也可以是一个str", **video_kwargs},
                    {'type': 'image', 'image': "这里的image_content既可以是一个image.image对象，也可以是一个str路径","min_pixels": self.min_pixels,"max_pixels": self.max_pixels},
                    {'type': 'text', 'text': text}

                    # document信息
                    {'type': 'text', 'text': "<Document>:"},
                    {'type': 'video', 'video': "这里既可以是一个列表list，也可以是一个str", **video_kwargs},
                    {'type': 'image', 'image': "这里的image_content既可以是一个image.image对象，也可以是一个str路径","min_pixels": self.min_pixels,"max_pixels": self.max_pixels},
                    {'type': 'text', 'text': text}
                ]
            }
        ]
        """
        inputs = []
        # 添加系统提示词？
        inputs.append({
            "role": "system",
            "content": [{
                "type": "text",
                "text": "Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
            }
            ]
        })
        if isinstance(query_text, tuple):
            instruct, query_text = query_text
        else:
            instruct = instruction
        # 1、添加指令instruct
        contents = []
        contents.append({
            "type": "text",
            "text": '<Instruct>: ' + instruct
        })
        # 2、处理query
        query_content = self.format_mm_content(
            query_text, query_image, query_video, prefix='<Query>:', 
            fps=fps, max_frames=max_frames
        )
        contents.extend(query_content)
        # 3、处理document
        doc_content = self.format_mm_content(
            doc_text, doc_image, doc_video, prefix='\n<Document>:', 
            fps=fps, max_frames=max_frames
        )
        contents.extend(doc_content)
        # 返回input
        inputs.append({
            "role": "user",
            "content": contents
        })
        return inputs

    def process(
        self,
        inputs,
    ) -> list[torch.Tensor]:
        """
        模型的输入被传递到这里面进行一系列的处理
        """
        instruction = inputs.get('instruction', self.default_instruction)

        # 这里获取到的query是一个字典，可能为{"text":xx,"image":image.image}这种形式
        query = inputs.get("query", {})
        # 这里获取到的documents是一个列表，可能为[{"text":xx,"image":image.image},{"text":xx,"image":image.image}]这种形式
        documents = inputs.get("documents", [])
        if not query or not documents:
            return []

        # 其实这个字典中可以存放{"text":xxx,"image":xxx,"video":xxx}
        # 这一步的目的是把query和每一个document拼接成为一对一对的形式
        pairs = [self.format_mm_instruction(
            query.get('text', None),
            query.get('image', None),
            query.get('video', None),
            document.get('text', None),
            document.get('image', None),
            document.get('video', None),
            instruction=instruction,
            fps=inputs.get('fps', self.fps),
            max_frames=inputs.get('max_frames', self.max_frames)
        ) for document in documents]

        final_scores = []
        # 对每对的内容进行tokennize，但是每对，好像是独立进行计算的。候选文档之间是没有任何关系的
        for pair in pairs:
            # 进行tokenizer
            inputs = self.tokenize([pair])
            # 把tokenizer的数字内容放大到显存上
            inputs = inputs.to(self.model.device)
            scores = self.compute_scores(inputs)
            final_scores.extend(scores)
        
        # 最后返回相关的分数
        return final_scores