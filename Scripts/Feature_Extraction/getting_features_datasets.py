import numpy as np
from skimage.io import imread
import tensorflow as tf
import tensorflow_hub as hub
import glob, time, json, re, os, sys
import pickle
from random import uniform
from math import pi
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
flags.DEFINE_integer('parallel',4,'Number of parallel batches')
flags.DEFINE_integer('prefetch',2,'How many batches should be prefetched')
flags.DEFINE_boolean('rotation',True,'Should the images be rotated')
#json_path = '../../Data/Json/train.json'
#resized_image_dir = '../../Data/Images/224/Train/'
#feature_dir = '../../Data/Features/224/Train/'
#module_url = 'https://tfhub.dev/google/imagenet/mobilenet_v1_025_224/feature_vector/1'

json_path = FLAGS.json_path
resized_image_dir = FLAGS.image_dir
feature_dir = FLAGS.output_dir
module_url = FLAGS.model

batch_size = FLAGS.batch_size

pickle_file = module_url.split('/')[5]+"_datasets"+'.pickle'

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


# pre_data = [[file_id[i],file_list[i],label_list[i]] for i in range(len(file_id))]

'''
Make the graph that basically only holds the module
Note in the graph the module works on a placeholder
Since we do not know howmany images we will process at a time,
we set the first parameter in the shape to be None
This placeholder will later on be filled with images
'''



tf.reset_default_graph()

datagen = tf.keras.preprocessing.image.ImageDataGenerator(
    rotation_range=15,
    horizontal_flip=True)

def _parse_image(file_id, filename, label_list):
    img_file = tf.read_file(filename,'image_reader')
    img_decode = tf.image.decode_image(img_file,name='image_decoder')
    if FLAGS.rotation:
        img_decode = tf.image.random_flip_left_right(img_decode)
        uniform_draw = tf.random_uniform([1],-pi*30/360,pi*30/360,name='Random_Draw_uniform')
        img_decode = tf.contrib.image.rotate(img_decode,uniform_draw,name='random_rotation')
	
    # Here something to change the images.
    # Randomly? I was thinking about 
    # tf.contrib.images.rotate
    # tf.image.flip_right_left

    return file_id, img_decode, label_list

# So here we want to insert the images.

with tf.name_scope('training_data') as scope:
    ds = tf.data.Dataset.from_tensor_slices((file_id, file_list, label_list))
    ds = ds.apply(tf.contrib.data.map_and_batch(map_func=_parse_image,batch_size=FLAGS.batch_size,num_parallel_batches=FLAGS.parallel))
    #ds = ds.map(_parse_image)

    #ds = ds.batch(batch_size)
    ds = ds.prefetch(FLAGS.prefetch)

    ds_iterator = tf.data.Iterator.from_structure(ds.output_types, ds.output_shapes)
    ds_next_element = ds_iterator.get_next()
    ds_init_op = ds_iterator.make_initializer(ds)
    


module = hub.Module(module_url)
images = tf.placeholder(shape=[None, 224,224,3], dtype=tf.float32, name='input')
features = module(images)

init_op = tf.global_variables_initializer()

times = []


with tf.Session() as sess:
  sess.run(init_op)
  
  # Finalize graph so that we not accidentely extend it. 
  sess.graph.finalize()


  sess.run(ds_init_op) 

  for j in range(max_iter):
    start = time.time()
    print('-'*50)
    print('Running iteration: {} of {}'.format(j+1, max_iter))
    
    # Get the image_names, labels and ids for this iteration

    
    ids, imgs, labels = sess.run(ds_next_element)    
    
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
    if os.path.exists(pickle_file):
        print(pickle_file)
        with open(pickle_file++str(j),'rb') as rfp: 
            results = pickle.load(rfp)
    else:
        results = []
    
    results.append(data)
   # print(pickle_file)

    with open(pickle_file+str(j),'wb+') as wfp:
        pickle.dump(results, wfp)

    print(time.time()-start)
    print('Estimated time left: {:.2f} seconds'.format( (len(file_list)-batch_size*(1+j))*sum(times)/(batch_size*(j+1)) ) )
