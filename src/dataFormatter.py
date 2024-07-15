import random
from datasets import load_dataset, Dataset
from configBase import ConfigBase
from mt import MT

class DataFormatter(ConfigBase):
  '''Handles training and inference data
  loading, processing, and formatting.'''
  def configure(self):
    self.dfCf = self.cp['dataFormatter']
    self.delim = self.dfCf['delim']
    self.inputTemple = self.dfCf[f'inputTemple{self.type.value}']
    self.respTemple = self.dfCf[f'respTemple{self.type.value}']
    self.load()
    if (self.cp['train']['packing'] == 'True'):
      self.getExamples = self.formatInput
    else: self.getExamples = self.unpackedProcessing

  def load(self, threshold: int = None, shuffle = True):
    '''loads dataset'''
    if not self.quiet: self.printHeader('Loading Data')
    dsDict = load_dataset(self.paths['data'])
    # filter by quality
    if 'eval' in self.paths['data']: return # no need to load here
    if not threshold: threshold = int(self.dfCf['qualityThreshold'])
    dsDict = dsDict.filter(lambda row: float(row['quality']) >= threshold)
    if shuffle: dsDict = dsDict.shuffle(seed=42) # 42. why not?

    if len(dsDict) == 1:
      if not self.quiet: self.printHeader('Splitting data')
      key = [split for split in dsDict][0]
      evalToTrainRatio = 0.001 if self.mode == 'test' else float(self.dfCf['evalToTrainRatio'])
      dsDict = dsDict[key].train_test_split(test_size = evalToTrainRatio)
    if not self.quiet:
      print('Results:')
      print(dsDict)
    
    self.trainDataset = dsDict['train']
    self.evalDataset = dsDict['test']

    if not self.quiet: print(f'''Loaded {len(self.trainDataset)} training and {len(self.evalDataset)} evaluation examples above at or above a quality of {threshold}''')

  def unpackedProcessing(self, examples) -> list:
    '''processes all data for training input'''
    output_texts = []
    # note that at this point, examples is a dictionary of lists. e.g.:
    # {'sentence': ['sent1', 'sent2' ...], 'answer': ['ans1', ...], ...}
    for i in range(len(examples['sentence'])):
      text = self.formatInput(examples, i)
      output_texts.append(text)
    return output_texts
    
  def getInputSample(self, i = 0):
    return self.formatInput([self.trainDataset][0], i)

  ### formatting f(x)s for input to various training phases
  def formatInput(self, example, i = 0,  formatFor: MT|None = None) -> str:
    '''Formats an example for training or for generation'''
    if formatFor == None: formatFor = self.type # default
    if isinstance(example['sentence'], list): # for unpacked processing
      # get column values from lists of strings
      context = f"{example['ref'][i]} - {example['sentence'][i]}"
      if formatFor != MT.E2E: answer = example['answer'][i]
      if formatFor == MT.QG: question = example['question'][i]
      if formatFor == MT.E2E: qa = example['qa'][i]
    else: # for packed processing or generation
        context = f"{example['ref']} - {example['sentence']}"
        if formatFor != MT.E2E: answer = example['answer']
        if formatFor == MT.QG: question = example['question']
        if formatFor == MT.E2E: qa = example['qa']
    # construct example
    templ = self.dfCf[f'inputTemple{formatFor.value}']
    templ = templ.replace('<context>', context)
    if formatFor != MT.E2E: templ = templ.replace('<answer>', answer)
    if formatFor == MT.QG: templ = templ.replace('<question>', question)
    if formatFor == MT.E2E: templ = templ.replace('<qa>', qa)
    return templ.strip()

  def getEvalInputs(self, evalDataset: Dataset = None) -> tuple[list[str], list[str]]:
    '''Processes the evaluation dataset into a prompt for
    the model using the current training format and a label
    (desired output). Used in custom NLG metrics.'''
    if evalDataset == None: evalDataset = self.evalDataset
    inputs = []; labels = []
    for row in evalDataset:
      example = self.formatInput(row).split(self.respTemple)
      inputs.append((example[0] + self.respTemple).strip())
      labels.append(example[1].strip())
    return (inputs, labels)
  
  ## output
  def getInferenceInput(self, dp) -> str:
    '''Returns a prompt for inference'''
    sampleMode = self.dfCf['sampleMode']
    match sampleMode:
      case 'generate':
        input()
        templ = self.inputTemple
      case 'manual':
        templ = input(f'> ')
        print('↓')
    if self.type == MT.AE:
      templ = templ.replace('<context>', dp.getRandomVerse().text)
      templ = templ.replace('<answer>', '')
    if self.type == MT.QG:
      row = random.randint(0, len(self.evalDataset) - 1)
      templ = templ.replace('<context>', self.evalDataset['sentence'][row])
      templ = templ.replace('<answer>', self.evalDataset['answer'][row])
      templ = templ.replace('<question>', '')
    if self.type == MT.E2E:
      verse = dp.getRandomVerse()
      templ = templ.replace('<context>', f'{verse.ref} - {verse.text}')
      templ = templ.replace('<qa>', '')
    return templ.strip()

if __name__ == '__main__':
  df = DataFormatter()
  df.printHeader('Testing DataFormatter')
  print(df.getInputSample())
