import ProgressReminder from '../progress-reminder';
import User from '../user';

import styled from './index.less';

const RightToolBar = () => {
  return (
    <div className={styled.toolbarWrapper}>
      <ProgressReminder />
      <User></User>
    </div>
  );
};

export default RightToolBar;
