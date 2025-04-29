from PhonebookProfileMethods import PhoneBookAccess

pbap = PhoneBookAccess(input('Enter the device address: '))
pbap.create_session()
 
while True:
      print("\n1. Select phonebook")
      print("2. Get size")
      print("3. List vcards")
      print("4. Pull vcard")
      print("5. Pull All ")
      print("6. Search")
      print("7. Get property")
      print('8. Display the filters')
      print('9. Exit')
      choice = input("Choose: ")
 
      if choice == "1":
         user_input=input('Select a repository -- Internal/sim1: ')
         folder=input('Enter which pbap object pb,ich,och,mch,fav,spd:')
         pbap.select_phonebook(user_input,folder)
 
      elif choice == "2":
         pbap.get_size()
      elif choice == "3":
         pbap.list_contacts()
      elif choice == '4':
         pbap.pull(input('Enter the vcard handle you want to pull :'))
      elif choice == '5':
         pbap.pull_all()
      elif choice == '6':
         searchfield=input('Enter the field for search operation :')
         searchvalue=input('Enter the value name/number/sound: ')
         pbap.search_contacts(searchfield,searchvalue)
      elif choice == '7':
         prop_name=input('Enter the property name :Folder/DatabaseIdentifier/PrimaryCounter/SecondaryCounter/FixedImageSize: ')
         pbap.get_property(prop_name)
      elif choice == '8':
         pbap.list_filters()
      elif choice == '9':
         pbap.disconnect()
         break


