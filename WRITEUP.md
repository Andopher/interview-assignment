# Project Writeup

## Approach & Assumptions

[Describe your overall approach to solving this problem. What was your thought process? What were the key challenges you identified?]

## Limitations & Future Improvements

[If you had more time, what would you improve?]

I took three different approaches to this issue before arriving at my solution:

First approach: ChatGPT Vision review with GPT-4o
I leveraged ChatGPT Vision (GPT-4o’s ability to assess images) by providing extensive guidelines and having it process the PDF page by page with minimal manual interaction—no iterative feedback loop. The results were quite good (around 75 % accuracy), but after a while no amount of prompt tweaking improved quality. Any gains became hyperspecific and hard-coded to individual scenarios, which isn’t sustainable long-term. I realized this wasn’t practical and that a more intuitive method might yield better results.

Second approach: Manufacturer-by-manufacturer JSON rules + ChatGPT Vision review
Recognizing that PDFs vary wildly except for each manufacturer’s dedicated pages, I built a .json of manufacturer-specific instructions. I then ran each page through ChatGPT Vision, guided by the matching JSON rules. While accuracy improved over time as the JSON grew, it still demanded substantial manual setup—and layouts can change, so it never became fully automatic.

Third approach: Logo-and-name top-of-page isolation + ChatGPT Vision review
Drawing on consumer-econ insights, I noted that every product page has the company logo and product name at the top. First, I filtered out non-product pages by scanning for submission-standard text (no LLM needed), cutting down pages significantly. Then, for the remaining candidates, I trimmed the top region—where the logo/name live—and sent that image snippet to ChatGPT Vision with clear guidelines (“logo and product name present at top”). Simplifying the image drastically boosted accuracy, since the model only needed to confirm and extract those key elements. This hybrid pre-filter + Vision review yielded the best results with every product being counted after running multiple times and the onyl slight being a handful of false positives that are a subproduct of a larger product, and some subproducts being generalized to a larger product. 

Future refinement
Given more time, I’d automatically detect the manufacturer name in the text, look up its known logo/name coordinates, crop exactly that region, and run the Vision review. This would prevent any false positive product pages as if the logo and name wee not present in the set locations it would not be added to the csv. New manufacturers could be added dynamically, making the whole pipeline fully automatic except when truly novel layouts appear.
