import sys, pandas as pd, random, csv
from datasets import load_dataset, Dataset
from qagBase import QAGBase

class DataProcessor(QAGBase):
  def configure(self):
    self.dpCf = self.cp['dataProcessor']
    self.source = self.dpCf['dpSource']
    self.destination = self.dpCf['dpDest']
    
    bibleDataSource = '../data/bible/nkjv.csv'
    self.nkjv = pd.read_csv(bibleDataSource)
    self.nkjvInfo = self.getNkjvInfo()


  # creates an object representing the NKJV Bible
  def getNkjvInfo(self):
    filePath = f'{self.dpCf["qagData"]}/bible/nkjv.csv'
    nkjvContent = {}

    with open(filePath, 'r', encoding='utf-8') as csvFile:
      reader = csv.reader(csvFile)
      next(reader)  # Skip header row

      for row in reader:
        book, chapter, verse, text = row
        chapter = int(chapter)
        verse = int(verse)

        if book not in nkjvContent:
          nkjvContent[book] = {'numChapters': 0}

        if chapter > nkjvContent[book]['numChapters']:
          nkjvContent[book]['numChapters'] = chapter

        if chapter not in nkjvContent[book]:
          nkjvContent[book][chapter] = 0

        nkjvContent[book][chapter] = max(nkjvContent[book][chapter], verse)

    return nkjvContent

  def qgToAE(self):
    dataset = load_dataset(self.source)
    df = dataset['train'].to_pandas()
    df = df[['answer', 'question','sentence']]
    grouped = df.groupby('sentence').agg({
      'answer': lambda x: ' <sep> '.join(set(x)), 
      'question': 'count'
    }).reset_index()
    grouped.rename(columns={'question': 'count'}, inplace=True)
    print(f'Mean Q&A per context: {grouped["count"].mean()}')
    print(grouped.head())
    print(len(grouped))
    dataset = Dataset.from_pandas(grouped.reset_index(drop=True))
    print(dataset)
    dataset.to_json(f"{self.destination}/data.jsonl")
    
  def pbeContextualize(self):
    data = pd.read_csv(f'{self.source}/refQuestions.csv')
    data['sentence'] = ''; data['paragraph'] = ''; data['paragraph_question'] = ''; data['paragraph_sentence'] = ''
    if not self.quiet: print(f'dataset length: {len(data.index)}')

    maximum = len(data.index)
    for i, row in data.iterrows():
      # show progress
      self.printProgressBar(i, maximum = maximum, label = 'context', width = 75)
      # get verse pieces
      book = row['book']; chapter = row['chapter']; verse = row['verse']; end = row['endVerse']
      previousNum = verse - 1 if verse > 1 else None
      followingNum = end + 1 if self.nkjvInfo[book][chapter] > end else None
      previous = self.getVerse(book, chapter, previousNum) + ' ' if previousNum else ''
      sentence = self.getVerse(book, chapter, verse, endVerse=end)
      following = ' ' + self.getVerse(book, chapter, followingNum) if followingNum else ''
      # assign pieces
      data.at[i, 'sentence'] = sentence
      data.at[i, 'paragraph'] = previous + sentence + following
      data.at[i, 'paragraph_question'] = f'question: {row["question"]}, context: {row["paragraph"]}'
      data.at[i, 'paragraph_sentence'] = f'{previous}<hl> {sentence} <hl>{following}'
    self.printProgressBar(maximum, maximum = maximum, label = 'context', width = 75) # done
    print('\n')
    # reorganize columns
    cols = ['answer', 'paragraph_question', 'question', 'sentence', 'paragraph', 'paragraph_sentence', 'points', 'source', 'quality']
    data = data[cols]
    if not self.quiet: print(data.head())
    # drop rows that we can't get references for
    data = data.dropna(subset=['paragraph_question', 'sentence', 'paragraph', 'paragraph_sentence'])
    # save
    data.to_csv(f'{self.destination}/contextQuestions.csv', index=False)

  def getVerse(self, book, chapter, startVerse, endVerse = None):
    # default to start verse
    endVerse = endVerse if endVerse else startVerse

    result = ''
    for verseNumber in range(startVerse, endVerse + 1):
      result += self.nkjv.loc[
        (self.nkjv['verseNumber'] == verseNumber)
        & (self.nkjv['book'] == book)
        & (self.nkjv['chapterNumber'] == chapter)
      , 'verse'].values[0]
    return result

  def getRandomVerse(self): 
    book = random.choice(self.nkjv['book'].unique())
    df = self.nkjv.loc[self.nkjv['book'] == book]
    chapter = random.choice(df['chapterNumber'].unique())
    df = df.loc[df['chapterNumber'] == chapter]
    verse = random.choice(df['verseNumber'].unique())
    return df.loc[df['verseNumber'] == verse].values[0][-1]

if __name__ == '__main__':
  dp = DataProcessor()
  match sys.argv[1].replace('-', ''):
    case 'randomVerse': print(dp.getRandomVerse())
    case 'qgToAE': dp.qgToAE()
    case 'pbeContextualize': dp.pbeContextualize()
    case 'none' | _: pass


