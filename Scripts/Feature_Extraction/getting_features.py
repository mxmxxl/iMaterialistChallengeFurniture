import numpy as np
from skimage.io import imread
import tensorflow as tf
import tensorflow_hub as hub
import glob, time, json, re, os, sys
import pickle


'''
This code will parse a directory of images sized 224x224
and our put features calculated using a mobilenet module
'''



# Put the logging level of tensorflow on ERROR.
# Otherwise tf prints all the info of the module
tf.logging.set_verbosity(tf.logging.ERROR)


# Some paths variables that we need so that we can:
# - get labels
# - get the resized images
# - Save the newly calculated features
flags = tf.app.flags
FLAGS = flags.FLAGS
flags.DEFINE_string('json_path', 'default', 'path to the json file for label etc')
flags.DEFINE_string('image_dir', 'default', 'path to the images')
flags.DEFINE_string('output_dir', 'default', 'Where to put the features')
flags.DEFINE_string('model', 'default', 'Which model to use')
flags.DEFINE_integer('batch_size',100,'What batch size to use')

#json_path = '../../Data/Json/train.json'
#resized_image_dir = '../../Data/Images/224/Train/'
#feature_dir = '../../Data/Features/224/Train/'
#module_url = 'https://tfhub.dev/google/imagenet/mobilenet_v1_025_224/feature_vector/1'

json_path = FLAGS.json_path
resized_image_dir = FLAGS.image_dir
feature_dir = FLAGS.output_dir
module_url = FLAGS.model

batch_size = FLAGS.batch_size

pickle_file = module_url.split('/')[5]+'.pickle'

pickle_file = os.path.join(feature_dir,pickle_file)


not_test_bool = ('test' not in json_path)

# Open the json file and make a image_id -> label_id dictionary
with open(json_path,'r') as f:
  json_file = json.load(f)
  
if not_test_bool: 
  labels = json_file['annotations']
  labels_dict = {i['image_id']:i['label_id'] for i in labels}


# Get all the image names from the resized image directoy
file_list = glob.glob(os.path.join(resized_image_dir,'*.jpeg'))
print(len(file_list))

# Make and file_id list and label_list (Note in the same order as the file_list ;)) 
def get_label(i):
  res =  int(re.findall(r'/([0-9]*)\.jpeg',i)[0] )
  return res

file_id = [get_label(i) for i in file_list]

if not_test_bool:
  label_list = [labels_dict[i] for i in file_id]


# Check how many iterations we will do. 
max_iter = len(file_list)//batch_size +1

'''
Make the graph that basically only holds the module
Note in the graph the module works on a placeholder
  Since we do not know howmany images we will process at a time,
  we set the first parameter in the shape to be None
  This placeholder will later on be filled with images


Module_256 is the module from tensorhub
  This will spit out a 256 feature vector called the features

'''
tf.reset_default_graph()
module = hub.Module(module_url)
images = tf.placeholder(shape=[None, 224,224,3], dtype=tf.float32, name='input')
features = module(images)

init_op = tf.global_variables_initializer()

times = []


with tf.Session() as sess:
  sess.run(init_op)
  
  # Finalize graph so that we not accidentely extend it. 
  sess.graph.finalize()

  for j in range(max_iter):
    start = time.time()
    print('-'*50)
    print('Running iteration: {} of {}'.format(j, max_iter))
    
    # Get the image_names, labels and ids for this iteration
    end = min(len(file_list),(j+1)*batch_size)
    files = file_list[j*batch_size:end]
    if not_test_bool:
      labels = label_list[j*batch_size:end]
    
    ids = file_id[j*batch_size:end]
    
    # Make a numpy array of all the data.
    imgs = np.array([imread(f) for f in files])
    
    # Put the images in the grapg get the feature back
    print('Getting features:')
    feat= sess.run(features, feed_dict={images:imgs})
  
    # For bookkeeping put the ids and the labels also with the data.
    if not_test_bool:
        data = np.c_[ids,feat,labels]
    else:
        data = np.c_[ids,feat]

    iter_time = time.time()-start
    times.append(iter_time)
    print('{:.2f} seconds'.format(iter_time))
    
    # Update pickle file
    '''
    if os.path.exists(pickle_file):
        with open(pickle_file,'rb') as rfp: 
            results = pickle.load(rfp)
    else:
        results = []

    results.append(data)
    '''
    
    with open(pickle_file+str(j),'wb') as wfp:
        pickle.dump(data, wfp)

    print('Estimated time left: {:.2f} seconds'.format( (len(file_list)-batch_size*(j+1))*sum(times)/(batch_size*(j+1)) ) )
